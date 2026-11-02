from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_is_instance,
	assert_not_eq,
	assert_not_in,
	assert_not_none,
	assert_raises,
	assert_that,
)
import time_machine

from helios.app import Application, Provider
from helios.app import Config as AppConfig
from helios.http import Headers, Method, Request, Response, Status
from helios.http.body import Stream
from helios.http.error import NotFoundError
from helios.routing import Route, Router
import helios.session
from helios.session import Flash
from helios.session.driver import Driver, memory
from helios.session.session import Session
from helios.session.sessions import Sessions
from helios.url import URL
from helios.view import Component
import helios.view.config
import helios.view.provider
from helios.view.views import Views

MAXIMUM_AGE = timedelta(days=30)
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class Notice(Component):
	template = "notice"

	label: str


def request(token: str | None = None) -> Request:
	headers = Headers()
	if token is not None:
		headers["Cookie"] = f"session_id={token}"
	return Request(Method.GET, URL("/"), headers)


def provider(secure: bool = False) -> helios.session.Provider:
	return helios.session.Provider(
		helios.session.Config(
			memory.Config(),
			secure=secure,
			maximum_age=MAXIMUM_AGE,
		)
	)


def exercise(
	request: Request,
	change=None,
	stored: list[Session] | None = None,
	secure: bool = False,
	resolve: bool = True,
):
	seen = []

	def index(request, context):
		if resolve:
			session = context.get(Session)
			seen.append(session)
			if change is not None:
				change(session, context.get(Sessions))
		return Response.empty()

	app = Application(
		AppConfig(),
		Router([Route.get("/", index)]),
		[provider(secure)],
	)
	driver = app.container.get(Driver)
	for session in stored or []:
		driver.write(session)
	app.boot()
	try:
		response = app.handle(request)
	finally:
		app.close()
	return (seen[0] if seen else None), response, cast(memory.Driver, driver)


def test_unused_and_empty_sessions_do_not_write():
	_, unused_response, unused_driver = exercise(request(), resolve=False)
	empty, empty_response, empty_driver = exercise(request())

	assert_not_in("session_id", unused_response.cookies)
	assert_not_in("session_id", empty_response.cookies)
	assert_not_none(empty)
	assert_eq(unused_driver.sessions, {})
	assert_eq(empty_driver.sessions, {})


def test_request_that_writes_no_session_does_not_purge():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	expired = Session(
		"expired-token",
		last_active_at=now - MAXIMUM_AGE - timedelta(microseconds=1),
	)

	with time_machine.travel(now, tick=False):
		_, _, driver = exercise(
			request(),
			lambda session, sessions: None,
			stored=[expired],
		)

	assert_not_none(driver.read("expired-token"))


def test_stores_data_and_sets_cookie_policy():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(now, tick=False):
		session, response, driver = exercise(
			request(),
			lambda session, sessions: session.__setitem__("message", "Hello"),
			secure=True,
		)

	stored = assert_not_none(driver.read(session.token))
	cookie = response.cookies["session_id"]
	assert_eq(stored.items, {"message": "Hello"})
	assert_eq(stored.last_active_at, now)
	assert_eq(cookie.value, session.token)
	assert_that(cookie.http_only)
	assert_that(cookie.secure)
	assert_eq(cookie.same_site, "Lax")
	assert_eq(cookie.expires, now + MAXIMUM_AGE)


def test_reuses_touches_and_rotates_known_session():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	known = Session(
		"visitor-token",
		{"message": "Hello"},
		last_active_at=now - timedelta(days=1),
	)
	with time_machine.travel(now, tick=False):
		session, response, driver = exercise(
			request("visitor-token"),
			lambda session, sessions: sessions.rotate(session),
			stored=[known],
		)

	stored = assert_not_none(driver.read(session.token))
	assert_not_eq(session.token, "visitor-token")
	assert_is(driver.read("visitor-token"), None)
	assert_eq(stored.items, {"message": "Hello"})
	assert_eq(stored.last_active_at, now)
	assert_eq(response.cookies["session_id"].value, session.token)


def test_replaces_and_clears_an_unknown_cookie():
	session, response, driver = exercise(request("unknown-token"))

	assert_not_eq(session.token, "unknown-token")
	assert_eq(driver.sessions, {})
	assert_eq(response.cookies["session_id"].value, "")
	assert_eq(response.cookies["session_id"].expires, EPOCH)


def test_purges_expired_sessions_and_renews_boundary():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	active = Session(
		"active-token",
		{"message": "Hello"},
		last_active_at=now - MAXIMUM_AGE,
	)
	expired = Session(
		"expired-token",
		last_active_at=now - MAXIMUM_AGE - timedelta(microseconds=1),
	)
	with time_machine.travel(now, tick=False):
		session, _, driver = exercise(
			request("active-token"),
			stored=[active, expired],
		)

	assert_eq(session.token, "active-token")
	assert_eq(assert_not_none(driver.read("active-token")).last_active_at, now)
	assert_is(driver.read("expired-token"), None)


def test_clear_removes_persisted_session():
	known = Session("visitor-token", {"message": "Hello"})
	_, response, driver = exercise(
		request("visitor-token"),
		lambda session, sessions: session.clear(),
		stored=[known],
	)

	assert_eq(driver.sessions, {})
	assert_eq(response.cookies["session_id"].value, "")
	assert_eq(response.cookies["session_id"].expires, EPOCH)


def test_unexpected_exception_does_not_save():
	def fail(request, context):
		context.get(Session)["message"] = "After"
		raise RuntimeError("failure")

	app = Application(AppConfig(), Router([Route.get("/", fail)]), [provider()])
	driver = app.container.get(Driver)
	driver.write(Session("visitor-token", {"message": "Before"}))
	app.boot()
	try:
		response = app.handle(request("visitor-token"))
	finally:
		app.close()

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
	assert_eq(assert_not_none(driver.read("visitor-token"))["message"], "Before")


def test_raised_http_error_discards_mutation():
	def missing(request, context):
		context.get(Session)["message"] = "After"
		raise NotFoundError()

	app = Application(AppConfig(), Router([Route.get("/", missing)]), [provider()])
	driver = app.container.get(Driver)
	driver.write(Session("visitor-token", {"message": "Before"}))
	app.boot()
	try:
		response = app.handle(request("visitor-token"))
	finally:
		app.close()

	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(assert_not_none(driver.read("visitor-token"))["message"], "Before")
	assert_not_in("session_id", response.cookies)


def test_failure_after_the_session_middleware_discards_mutation():
	def refuse(request, context, next):
		next(request, context)
		raise NotFoundError()

	def change(request, context):
		context.get(Session)["message"] = "After"
		return Response.empty()

	app = Application(
		AppConfig(),
		Router([Route.get("/", change)]),
		[provider()],
		[refuse],
	)
	driver = app.container.get(Driver)
	driver.write(Session("visitor-token", {"message": "Before"}))
	app.boot()
	try:
		response = app.handle(request("visitor-token"))
	finally:
		app.close()

	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(assert_not_none(driver.read("visitor-token"))["message"], "Before")


def test_returned_error_response_saves_mutation():
	def failed(request, context):
		context.get(Session)["message"] = "Saved"
		return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

	app = Application(AppConfig(), Router([Route.get("/", failed)]), [provider()])
	driver = cast(memory.Driver, app.container.get(Driver))
	app.boot()
	try:
		response = app.handle(request())
	finally:
		app.close()

	token = response.cookies["session_id"].value
	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
	assert_eq(assert_not_none(driver.read(token))["message"], "Saved")


def test_flash_reaches_next_request_only():
	notices = []

	def create(request, context):
		context.get(Flash)["notice"] = "Saved"
		return Response.empty()

	def index(request, context):
		notices.append(context.get(Flash).get("notice"))
		return Response.empty()

	app = Application(
		AppConfig(),
		Router([Route.post("/", create), Route.get("/", index)]),
		[provider()],
	)
	app.boot()
	try:
		response = app.handle(Request(Method.POST, URL("/")))
		token = response.cookies["session_id"].value
		app.handle(request(token))
		app.handle(request(token))
	finally:
		app.close()

	assert_eq(notices, ["Saved", None])


def test_failed_request_keeps_unread_flash():
	notices = []

	def missing(request, context):
		notices.append(context.get(Flash).get("notice"))
		raise NotFoundError()

	app = Application(AppConfig(), Router([Route.get("/", missing)]), [provider()])
	app.container.get(Driver).write(
		Session("visitor-token", {"_flash": {"notice": "Saved"}})
	)
	app.boot()
	try:
		app.handle(request("visitor-token"))
		app.handle(request("visitor-token"))
	finally:
		app.close()

	assert_eq(notices, ["Saved", "Saved"])


def test_shares_flash_with_views():
	with TemporaryDirectory() as directory:
		views_directory = Path(directory)
		views_directory.joinpath("index.html").write_text('{{ flash.get("notice") }}')

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			AppConfig(),
			Router([Route.get("/", index)]),
			[
				provider(),
				helios.view.provider.Provider(
					helios.view.config.Config(views_directory)
				),
			],
		)
		app.container.get(Driver).write(
			Session("visitor-token", {"_flash": {"notice": "Saved"}})
		)
		app.boot()
		try:
			response = app.handle(request("visitor-token"))
		finally:
			app.close()

	assert_eq(str(response.body), "Saved")


def test_shares_flash_with_components():
	with TemporaryDirectory() as directory:
		views_directory = Path(directory)
		views_directory.joinpath("index.html").write_text(
			'{{ Notice(label="Notice") }}'
		)
		views_directory.joinpath("notice.html").write_text(
			'{{ label }}: {{ flash.get("notice") }}'
		)

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			AppConfig(),
			Router([Route.get("/", index)]),
			[
				provider(),
				helios.view.provider.Provider(
					helios.view.config.Config(views_directory),
					components=[Notice],
				),
			],
		)
		app.container.get(Driver).write(
			Session("visitor-token", {"_flash": {"notice": "Saved"}})
		)
		app.boot()
		try:
			response = app.handle(request("visitor-token"))
		finally:
			app.close()

	assert_eq(str(response.body), "Notice: Saved")


def test_boots_without_views():
	notices = []

	def index(request, context):
		notices.append(context.get(Flash).get("notice"))
		return Response.empty()

	app = Application(AppConfig(), Router([Route.get("/", index)]), [provider()])
	app.container.get(Driver).write(
		Session("visitor-token", {"_flash": {"notice": "Saved"}})
	)
	app.boot()
	try:
		app.handle(request("visitor-token"))
	finally:
		app.close()

	assert_eq(notices, ["Saved"])


def test_provider_registers_config_before_boot():
	config = helios.session.Config(memory.Config())

	app = Application(AppConfig(), Router([]), [helios.session.Provider(config)])

	assert_is(app.container.get(helios.session.Config), config)


class Outer(Provider):
	"""Runs a middleware outside the session middleware."""

	def __init__(self, middleware):
		self.middleware = middleware

	def boot(self, application: Application):
		application.use(self.middleware)


def handle(route, outer=None) -> Response:
	providers = [Outer(outer)] if outer is not None else []
	app = Application(
		AppConfig(),
		Router([Route.get("/", route)]),
		[*providers, provider()],
	)
	app.boot()
	try:
		return app.handle(request())
	finally:
		app.close()


def test_streamed_body_cannot_write_to_the_session():
	errors = []

	def stream(request, context):
		session = context.get(Session)
		session["message"] = "Hello"

		def chunks():
			try:
				session["late"] = "Too late"
			except RuntimeError as error:
				errors.append(error)
			yield b""

		return Response.stream(chunks(), "text/plain")

	response = handle(stream)
	assert_is_instance(response.body, Stream)
	list(cast(Stream, response.body).chunks)

	assert_eq([type(error) for error in errors], [RuntimeError])


def test_streamed_body_cannot_write_to_the_flash():
	errors = []

	def stream(request, context):
		flash = context.get(Flash)

		def chunks():
			try:
				flash["notice"] = "Too late"
			except RuntimeError as error:
				errors.append(error)
			yield b""

		return Response.stream(chunks(), "text/plain")

	response = handle(stream)
	assert_is_instance(response.body, Stream)
	list(cast(Stream, response.body).chunks)

	assert_eq([type(error) for error in errors], [RuntimeError])


def test_failed_request_closes_its_sessions():
	captured = []

	def fail(request, context):
		captured.append(context.get(Sessions))
		captured.append(context.get(Session))
		raise NotFoundError()

	handle(fail)

	sessions, session = captured
	with assert_raises(RuntimeError) as save:
		sessions.save(Session("other-token"))
	with assert_raises(RuntimeError) as write:
		session["message"] = "Hello"
	assert_is(type(save.exception), RuntimeError)
	assert_is(type(write.exception), RuntimeError)


def test_outer_middleware_cannot_write_to_the_flash():
	errors = []

	def outer(request, context, next):
		response = next(request, context)
		try:
			context.get(Flash)["notice"] = "Too late"
		except RuntimeError as error:
			errors.append(error)
		return response

	def index(request, context):
		context.get(Flash)
		return Response.empty()

	handle(index, outer)

	assert_eq([type(error) for error in errors], [RuntimeError])


def test_outer_middleware_cannot_rotate_the_session():
	errors = []

	def outer(request, context, next):
		response = next(request, context)
		try:
			context.get(Sessions).rotate(context.get(Session))
		except RuntimeError as error:
			errors.append(error)
		return response

	def index(request, context):
		context.get(Session)["message"] = "Hello"
		return Response.empty()

	handle(index, outer)

	assert_eq([type(error) for error in errors], [RuntimeError])
