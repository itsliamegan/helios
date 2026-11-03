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

import helios.app
from helios.app import Config as AppConfig
from helios.app import Provider
from helios.http import Headers, Method, Request, Response, Status
from helios.http.body import Stream
from helios.http.error import NotFoundError
from helios.routing import Route, Router
import helios.session
from helios.session import Flash
from helios.session.driver import memory
from helios.session.session import Session
from helios.session.sessions import Sessions
from helios.session.token import Token
from helios.url import URL
from helios.view import Component
import helios.view.config
import helios.view.provider
from helios.view.views import Views
import helios.wsgi
from helios.wsgi.test import TestClient

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


def application(
	routes: list[Route],
	providers: list[Provider] | None = None,
	middlewares=None,
) -> helios.wsgi.Application:
	app = helios.wsgi.Application(
		AppConfig(),
		Router(routes),
		[provider(), *(providers or [])],
		middlewares,
	)
	app.boot()
	return app


def show_message(request, context) -> Response:
	session = context.get(Session)
	if "message" in session:
		return Response.text(session["message"])
	else:
		return Response.text("")


def exercise(
	request: Request,
	change=None,
	secure: bool = False,
	resolve: bool = True,
):
	seen = []

	def index(request, context):
		if resolve:
			session = context.get(Session)
			seen.append(session)
			if change is not None:
				sessions = context.get(Sessions)
				change(session, sessions)
		return Response.empty()

	app = helios.app.Application(
		AppConfig(),
		Router([Route.get("/", index)]),
		[provider(secure)],
	)
	app.boot()
	try:
		response = app.handle(request)
	finally:
		app.close()
	return (seen[0] if seen else None), response


def test_unused_and_empty_sessions_set_no_cookie():
	_, unused_response = exercise(request(), resolve=False)
	empty, empty_response = exercise(request())

	assert_not_in("session_id", unused_response.cookies)
	assert_not_in("session_id", empty_response.cookies)
	assert_not_none(empty)


def test_sets_the_cookie_policy():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(now, tick=False):
		session, response = exercise(
			request(),
			lambda session, sessions: session.__setitem__("message", "Hello"),
			secure=True,
		)

	cookie = response.cookies["session_id"]
	assert_eq(cookie.value, session.token.plaintext)
	assert_that(cookie.http_only)
	assert_that(cookie.secure)
	assert_eq(cookie.same_site, "Lax")
	assert_eq(cookie.expires, now + MAXIMUM_AGE)


def test_saves_a_session_with_items():
	def create(request, context):
		session = context.get(Session)
		session["message"] = "Hello"
		return Response.empty()

	client = TestClient(
		application([Route.post("/", create), Route.get("/", show_message)])
	)

	client.post("/")
	response = client.get("/")

	assert_eq(response.text, "Hello")


def test_touches_a_found_session():
	seen = []

	def index(request, context):
		session = context.get(Session)
		seen.append(session.last_active_at)
		return Response.empty()

	client = TestClient(application([Route.get("/", index)]))
	created = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(created, tick=False), client.session() as session:
		session["message"] = "Hello"

	visited = created + timedelta(days=1)
	with time_machine.travel(visited, tick=False):
		client.get("/")

	assert_eq(seen, [visited])


def test_rotates_a_session_to_a_new_token():
	def rotate(request, context):
		session = context.get(Session)
		sessions = context.get(Sessions)
		sessions.rotate(session)
		return Response.empty()

	app = application([Route.post("/", rotate), Route.get("/", show_message)])
	client = TestClient(app)
	with client.session() as session:
		session["message"] = "Hello"
	old_token = assert_not_none(client.get_cookie("session_id")).value

	client.post("/")
	stale = TestClient(app)
	stale.set_cookie("session_id", old_token)

	assert_not_eq(assert_not_none(client.get_cookie("session_id")).value, old_token)
	assert_eq(client.get("/").text, "Hello")
	assert_eq(stale.get("/").text, "")


def test_replaces_and_clears_an_unknown_cookie():
	session, response = exercise(request("unknown-token"))

	assert_not_eq(session.token, Token.from_plaintext("unknown-token"))
	assert_eq(response.cookies["session_id"].value, "")
	assert_eq(response.cookies["session_id"].expires, EPOCH)


def test_finds_a_session_active_at_the_maximum_age():
	client = TestClient(application([Route.get("/", show_message)]))
	created = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(created, tick=False), client.session() as session:
		session["message"] = "Hello"

	with time_machine.travel(created + MAXIMUM_AGE, tick=False):
		response = client.get("/")

	assert_eq(response.text, "Hello")


def test_purges_expired_sessions_when_a_request_saves_a_session():
	def create(request, context):
		session = context.get(Session)
		session["message"] = "Other"
		return Response.empty()

	app = application([Route.post("/", create), Route.get("/", show_message)])
	expired = TestClient(app)
	other = TestClient(app)
	created = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(created, tick=False), expired.session() as session:
		session["message"] = "Hello"

	with time_machine.travel(
		created + MAXIMUM_AGE + timedelta(microseconds=1),
		tick=False,
	):
		other.post("/")

	# Back within the maximum age, only a purged session is missing.
	with time_machine.travel(created, tick=False):
		response = expired.get("/")

	assert_eq(response.text, "")


def test_request_that_writes_no_session_does_not_purge():
	def resolve(request, context):
		context.get(Sessions)
		return Response.empty()

	app = application([Route.post("/", resolve), Route.get("/", show_message)])
	kept = TestClient(app)
	other = TestClient(app)
	created = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(created, tick=False), kept.session() as session:
		session["message"] = "Hello"

	with time_machine.travel(
		created + MAXIMUM_AGE + timedelta(microseconds=1),
		tick=False,
	):
		other.post("/")

	# Back within the maximum age, a session that was not purged is found.
	with time_machine.travel(created, tick=False):
		response = kept.get("/")

	assert_eq(response.text, "Hello")


def test_clearing_a_session_destroys_it_and_its_cookie():
	def clear(request, context):
		session = context.get(Session)
		session.clear()
		return Response.empty()

	app = application([Route.post("/", clear), Route.get("/", show_message)])
	client = TestClient(app)
	with client.session() as session:
		session["message"] = "Hello"
	token = assert_not_none(client.get_cookie("session_id")).value

	client.post("/")
	stale = TestClient(app)
	stale.set_cookie("session_id", token)

	assert_is(client.get_cookie("session_id"), None)
	assert_eq(stale.get("/").text, "")


def test_unexpected_exception_does_not_save():
	def fail(request, context):
		session = context.get(Session)
		session["message"] = "After"
		raise RuntimeError("failure")

	client = TestClient(
		application([Route.post("/", fail), Route.get("/", show_message)])
	)
	with client.session() as session:
		session["message"] = "Before"

	failed = client.post("/")
	response = client.get("/")

	assert_eq(failed.status_code, Status.INTERNAL_SERVER_ERROR.code)
	assert_eq(response.text, "Before")


def test_raised_http_error_discards_mutation():
	def missing(request, context):
		session = context.get(Session)
		session["message"] = "After"
		raise NotFoundError()

	client = TestClient(
		application([Route.post("/", missing), Route.get("/", show_message)])
	)
	with client.session() as session:
		session["message"] = "Before"

	failed = client.post("/")
	response = client.get("/")

	assert_eq(failed.status_code, Status.NOT_FOUND.code)
	assert_is(failed.headers.get("Set-Cookie"), None)
	assert_eq(response.text, "Before")


def test_failure_after_the_session_middleware_discards_mutation():
	def refuse(request, context, next):
		response = next(request, context)
		if request.method is Method.POST:
			raise NotFoundError()
		return response

	def change(request, context):
		session = context.get(Session)
		session["message"] = "After"
		return Response.empty()

	client = TestClient(
		application(
			[Route.post("/", change), Route.get("/", show_message)],
			middlewares=[refuse],
		)
	)
	with client.session() as session:
		session["message"] = "Before"

	failed = client.post("/")
	response = client.get("/")

	assert_eq(failed.status_code, Status.NOT_FOUND.code)
	assert_eq(response.text, "Before")


def test_returned_error_response_saves_mutation():
	def failed(request, context):
		session = context.get(Session)
		session["message"] = "Saved"
		return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

	client = TestClient(
		application([Route.post("/", failed), Route.get("/", show_message)])
	)

	client.post("/")
	response = client.get("/")

	assert_eq(response.text, "Saved")


def test_flash_reaches_next_request_only():
	notices = []

	def create(request, context):
		flash = context.get(Flash)
		flash["notice"] = "Saved"
		return Response.empty()

	def index(request, context):
		flash = context.get(Flash)
		notices.append(flash.get("notice"))
		return Response.empty()

	client = TestClient(application([Route.post("/", create), Route.get("/", index)]))

	client.post("/")
	client.get("/")
	client.get("/")

	assert_eq(notices, ["Saved", None])


def test_failed_request_keeps_unread_flash():
	notices = []

	def create(request, context):
		flash = context.get(Flash)
		flash["notice"] = "Saved"
		return Response.empty()

	def missing(request, context):
		flash = context.get(Flash)
		notices.append(flash.get("notice"))
		raise NotFoundError()

	client = TestClient(application([Route.post("/", create), Route.get("/", missing)]))

	client.post("/")
	client.get("/")
	client.get("/")

	assert_eq(notices, ["Saved", "Saved"])


def test_shares_flash_with_views():
	def create(request, context):
		flash = context.get(Flash)
		flash["notice"] = "Saved"
		return Response.empty()

	def index(request, context):
		views = context.get(Views)
		return views.render("index")

	with TemporaryDirectory() as directory:
		views_directory = Path(directory)
		views_directory.joinpath("index.html").write_text('{{ flash.get("notice") }}')
		client = TestClient(
			application(
				[Route.post("/", create), Route.get("/", index)],
				[
					helios.view.provider.Provider(
						helios.view.config.Config(views_directory)
					),
				],
			)
		)

		client.post("/")
		response = client.get("/")

	assert_eq(response.text, "Saved")


def test_shares_flash_with_components():
	def create(request, context):
		flash = context.get(Flash)
		flash["notice"] = "Saved"
		return Response.empty()

	def index(request, context):
		views = context.get(Views)
		return views.render("index")

	with TemporaryDirectory() as directory:
		views_directory = Path(directory)
		views_directory.joinpath("index.html").write_text(
			'{{ Notice(label="Notice") }}'
		)
		views_directory.joinpath("notice.html").write_text(
			'{{ label }}: {{ flash.get("notice") }}'
		)
		client = TestClient(
			application(
				[Route.post("/", create), Route.get("/", index)],
				[
					helios.view.provider.Provider(
						helios.view.config.Config(views_directory),
						components=[Notice],
					),
				],
			)
		)

		client.post("/")
		response = client.get("/")

	assert_eq(response.text, "Notice: Saved")


def test_provider_registers_config_before_boot():
	config = helios.session.Config(memory.Config())

	app = helios.app.Application(
		AppConfig(),
		Router([]),
		[helios.session.Provider(config)],
	)

	assert_is(app.container.get(helios.session.Config), config)


class Outer(Provider):
	"""Runs a middleware outside the session middleware."""

	def __init__(self, middleware):
		self.middleware = middleware

	def boot(self, application: helios.app.Application):
		application.use(self.middleware)


def handle(route, outer=None) -> Response:
	providers = [Outer(outer)] if outer is not None else []
	app = helios.app.Application(
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
		sessions = context.get(Sessions)
		session = context.get(Session)
		captured.append(sessions)
		captured.append(session)
		raise NotFoundError()

	handle(fail)

	sessions, session = captured
	with assert_raises(RuntimeError) as save:
		sessions.save(Session(Token.from_plaintext("other-token")))
	with assert_raises(RuntimeError) as write:
		session["message"] = "Hello"
	assert_is(type(save.exception), RuntimeError)
	assert_is(type(write.exception), RuntimeError)


def test_outer_middleware_cannot_write_to_the_flash():
	errors = []

	def outer(request, context, next):
		response = next(request, context)
		try:
			flash = context.get(Flash)
			flash["notice"] = "Too late"
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
			sessions = context.get(Sessions)
			session = context.get(Session)
			sessions.rotate(session)
		except RuntimeError as error:
			errors.append(error)
		return response

	def index(request, context):
		session = context.get(Session)
		session["message"] = "Hello"
		return Response.empty()

	handle(index, outer)

	assert_eq([type(error) for error in errors], [RuntimeError])
