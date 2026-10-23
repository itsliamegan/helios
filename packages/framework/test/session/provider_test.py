from datetime import UTC, datetime, timedelta
import json
import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from typing import cast
from uuid import uuid4

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
from helios.http import Headers, Method, Request, Response, Status, URL
from helios.http.body import Stream
from helios.http.error import NotFoundError
from helios.routing import Route, Router
import helios.session
from helios.session import Flash
from helios.session.file import Driver
from helios.session.session import Session
from helios.session.sessions import Sessions
from helios.view import Component
import helios.view.config
import helios.view.provider
from helios.view.views import Views

MAXIMUM_AGE = timedelta(days=30)


class Notice(Component):
	template = "notice"

	label: str


def request(session_id: str | None = None) -> Request:
	headers = Headers()
	if session_id is not None:
		headers["Cookie"] = f"session_id={session_id}"
	return Request(Method.GET, URL("/"), headers)


def write_sessions(path: Path, sessions: dict | None = None):
	path.write_text(json.dumps(sessions or {}))


def read_sessions(path: Path):
	return json.loads(path.read_text())


def exercise(
	path: Path,
	request: Request,
	change=None,
	secure: bool = False,
	resolve: bool = True,
	maximum_age: timedelta = MAXIMUM_AGE,
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
		[
			helios.session.Provider(
				helios.session.Config(secure=secure, maximum_age=maximum_age),
				Driver(path, path.with_suffix(".lock")),
			)
		],
	)
	app.boot()
	try:
		response = app.handle(request)
	finally:
		app.close()
	return (seen[0] if seen else None), response


def session_data(
	items: dict | None = None,
	last_active_at: datetime | None = None,
):
	return {
		"items": items or {},
		"last_active_at": (
			last_active_at.isoformat() if last_active_at is not None else None
		),
	}


def test_unused_and_empty_sessions_do_not_write():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		before = path.stat().st_mtime_ns

		_, unused_response = exercise(path, request(), resolve=False)
		empty, empty_response = exercise(path, request())

		assert_not_in("session_id", unused_response.cookies)
		assert_not_in("session_id", empty_response.cookies)
		assert_not_none(empty)
		assert_eq(path.stat().st_mtime_ns, before)
		assert_eq(read_sessions(path), {})


def test_stores_data_and_sets_cookie_policy():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		now = datetime(2026, 10, 12, tzinfo=UTC)
		with time_machine.travel(now, tick=False):
			session, response = exercise(
				path,
				request(),
				lambda session, sessions: session.__setitem__("message", "Hello"),
				secure=True,
			)

		stored = read_sessions(path)
		cookie = response.cookies["session_id"]
		assert_eq(stored[str(session.id)]["items"], {"message": "Hello"})
		assert_eq(cookie.value, str(session.id))
		assert_that(cookie.http_only)
		assert_that(cookie.secure)
		assert_eq(cookie.same_site, "Lax")
		assert_eq(cookie.expires, now + MAXIMUM_AGE)


def test_reuses_touches_and_rotates_known_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		old_id = uuid4()
		write_sessions(path, {str(old_id): session_data({"message": "Hello"})})
		now = datetime(2026, 10, 12, tzinfo=UTC)
		with time_machine.travel(now, tick=False):
			session, response = exercise(
				path,
				request(str(old_id)),
				lambda session, sessions: sessions.rotate(session),
			)

		stored = read_sessions(path)
		assert_not_eq(session.id, old_id)
		assert_not_in(str(old_id), stored)
		assert_eq(stored[str(session.id)]["items"], {"message": "Hello"})
		assert_eq(stored[str(session.id)]["last_active_at"], now.isoformat())
		assert_eq(response.cookies["session_id"].value, str(session.id))


def test_replaces_malformed_and_unknown_cookies():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		malformed, _ = exercise(path, request("not-a-uuid"))
		unknown_id = uuid4()
		unknown, _ = exercise(path, request(str(unknown_id)))

		assert_not_eq(malformed.id, unknown_id)
		assert_not_eq(unknown.id, unknown_id)
		assert_eq(read_sessions(path), {})


def test_purges_expired_sessions_and_renews_boundary():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		now = datetime(2026, 10, 12, tzinfo=UTC)
		active_id = uuid4()
		expired_id = uuid4()
		write_sessions(
			path,
			{
				str(active_id): session_data({"message": "Hello"}, now - MAXIMUM_AGE),
				str(expired_id): session_data(
					last_active_at=now - MAXIMUM_AGE - timedelta(microseconds=1)
				),
			},
		)
		with time_machine.travel(now, tick=False):
			session, _ = exercise(path, request(str(active_id)))

		stored = read_sessions(path)
		assert_eq(session.id, active_id)
		assert_eq(stored[str(active_id)]["last_active_at"], now.isoformat())
		assert_not_in(str(expired_id), stored)


def test_clear_removes_persisted_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		write_sessions(path, {str(id): session_data({"message": "Hello"})})
		_, response = exercise(
			path, request(str(id)), lambda session, sessions: session.clear()
		)

		assert_eq(read_sessions(path), {})
		assert_eq(response.cookies["session_id"].value, "")
		assert_eq(
			response.cookies["session_id"].expires, datetime(1970, 1, 1, tzinfo=UTC)
		)


def test_unexpected_exception_does_not_save_and_releases_lock():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		initial = {str(id): session_data({"message": "Before"})}
		write_sessions(path, initial)

		def fail(request, context):
			context.get(Session)["message"] = "After"
			raise RuntimeError("failure")

		driver = Driver(path, path.with_suffix(".lock"))
		app = Application(
			AppConfig(),
			Router([Route.get("/", fail)]),
			[helios.session.Provider(helios.session.Config(), driver)],
		)
		app.boot()
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(read_sessions(path), initial)
		with driver.open() as store:
			assert_eq(store.get(id)["message"], "Before")


def test_raised_http_error_discards_mutation():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		initial = {str(id): session_data({"message": "Before"})}
		write_sessions(path, initial)

		def missing(request, context):
			context.get(Session)["message"] = "After"
			raise NotFoundError()

		app = Application(
			AppConfig(),
			Router([Route.get("/", missing)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		app.boot()
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

		assert_eq(response.status, Status.NOT_FOUND)
		assert_eq(read_sessions(path), initial)
		assert_not_in("session_id", response.cookies)


def test_releases_lock_when_request_fails_after_resolving_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		initial = {str(id): session_data({"message": "Before"})}
		write_sessions(path, initial)

		def refuse(request, context, next):
			next(request, context)
			raise NotFoundError()

		def change(request, context):
			context.get(Session)["message"] = "After"
			return Response.empty()

		driver = Driver(path, path.with_suffix(".lock"))
		app = Application(
			AppConfig(),
			Router([Route.get("/", change)]),
			[helios.session.Provider(helios.session.Config(), driver)],
			[refuse],
		)
		app.boot()
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

		assert_eq(response.status, Status.NOT_FOUND)
		assert_eq(read_sessions(path), initial)
		with driver.open() as store:
			assert_eq(store.get(id)["message"], "Before")


def test_returned_error_response_saves_mutation():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)

		def failed(request, context):
			context.get(Session)["message"] = "Saved"
			return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

		app = Application(
			AppConfig(),
			Router([Route.get("/", failed)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		app.boot()
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(
			next(iter(read_sessions(path).values()))["items"], {"message": "Saved"}
		)


def test_flash_reaches_next_request_only():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
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
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		app.boot()
		try:
			response = app.handle(Request(Method.POST, URL("/")))
			id = response.cookies["session_id"].value
			app.handle(request(id))
			app.handle(request(id))
		finally:
			app.close()

		assert_eq(notices, ["Saved", None])


def test_failed_request_keeps_unread_flash():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		write_sessions(path, {str(id): session_data({"_flash": {"notice": "Saved"}})})
		notices = []

		def missing(request, context):
			notices.append(context.get(Flash).get("notice"))
			raise NotFoundError()

		app = Application(
			AppConfig(),
			Router([Route.get("/", missing)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		app.boot()
		try:
			app.handle(request(str(id)))
			app.handle(request(str(id)))
		finally:
			app.close()

		assert_eq(notices, ["Saved", "Saved"])


def test_shares_flash_with_views():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		write_sessions(path, {str(id): session_data({"_flash": {"notice": "Saved"}})})
		views_directory = Path(directory, "views")
		views_directory.mkdir()
		views_directory.joinpath("index.html").write_text('{{ flash.get("notice") }}')

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			AppConfig(),
			Router([Route.get("/", index)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				),
				helios.view.provider.Provider(
					helios.view.config.Config(views_directory)
				),
			],
		)
		app.boot()
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

	assert_eq(str(response.body), "Saved")


def test_shares_flash_with_components():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		write_sessions(path, {str(id): session_data({"_flash": {"notice": "Saved"}})})
		views_directory = Path(directory, "views")
		views_directory.mkdir()
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
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				),
				helios.view.provider.Provider(
					helios.view.config.Config(views_directory),
					components=[Notice],
				),
			],
		)
		app.boot()
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

	assert_eq(str(response.body), "Notice: Saved")


def test_boots_without_views():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		id = uuid4()
		write_sessions(path, {str(id): session_data({"_flash": {"notice": "Saved"}})})
		notices = []

		def index(request, context):
			notices.append(context.get(Flash).get("notice"))
			return Response.empty()

		app = Application(
			AppConfig(),
			Router([Route.get("/", index)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		app.boot()
		try:
			app.handle(request(str(id)))
		finally:
			app.close()

	assert_eq(notices, ["Saved"])


def lock_worker(path: str, lock_path: str, queue):
	driver = Driver(Path(path), Path(lock_path))
	with driver.open():
		queue.put(("entered", time.monotonic()))
		time.sleep(0.15)
		queue.put(("leaving", time.monotonic()))


def test_file_driver_serializes_processes():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		lock_path = path.with_suffix(".lock")
		write_sessions(path)
		context = multiprocessing.get_context("fork")
		queue = context.Queue()
		first = context.Process(
			target=lock_worker, args=(str(path), str(lock_path), queue)
		)
		second = context.Process(
			target=lock_worker, args=(str(path), str(lock_path), queue)
		)
		first.start()
		first_event = queue.get(timeout=5)
		second.start()
		events = [first_event, *(queue.get(timeout=5) for _ in range(3))]
		first.join(timeout=5)
		second.join(timeout=5)

		assert_eq(first.exitcode, 0)
		assert_eq(second.exitcode, 0)
		assert_eq(
			[event[0] for event in events], ["entered", "leaving", "entered", "leaving"]
		)
		assert_that(events[2][1] >= events[1][1])


def test_provider_registers_config_before_boot():
	with TemporaryDirectory() as dir:
		path = Path(dir, "sessions.json")
		config = helios.session.Config()

		app = Application(
			AppConfig(),
			Router([]),
			[helios.session.Provider(config, Driver(path, path.with_suffix(".lock")))],
		)

		assert_is(app.container.get(helios.session.Config), config)


class Outer(Provider):
	"""Runs a middleware outside the session middleware."""

	def __init__(self, middleware):
		self.middleware = middleware

	def boot(self, application: Application):
		application.use(self.middleware)


def handle(path: Path, route, outer=None) -> Response:
	providers = [Outer(outer)] if outer is not None else []
	app = Application(
		AppConfig(),
		Router([Route.get("/", route)]),
		[
			*providers,
			helios.session.Provider(
				helios.session.Config(),
				Driver(path, path.with_suffix(".lock")),
			),
		],
	)
	app.boot()
	try:
		return app.handle(request())
	finally:
		app.close()


def test_streamed_body_cannot_write_to_the_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
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

			return Response.stream(chunks())

		response = handle(path, stream)
		assert_is_instance(response.body, Stream)
		list(cast(Stream, response.body).chunks)

		assert_eq([type(error) for error in errors], [RuntimeError])


def test_streamed_body_cannot_write_to_the_flash():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		errors = []

		def stream(request, context):
			flash = context.get(Flash)

			def chunks():
				try:
					flash["notice"] = "Too late"
				except RuntimeError as error:
					errors.append(error)
				yield b""

			return Response.stream(chunks())

		response = handle(path, stream)
		assert_is_instance(response.body, Stream)
		list(cast(Stream, response.body).chunks)

		assert_eq([type(error) for error in errors], [RuntimeError])


def test_failed_request_closes_its_sessions():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		captured = []

		def fail(request, context):
			captured.append(context.get(Sessions))
			captured.append(context.get(Session))
			raise NotFoundError()

		handle(path, fail)

		sessions, session = captured
		with assert_raises(RuntimeError) as put:
			sessions.put(Session(uuid4()))
		with assert_raises(RuntimeError) as write:
			session["message"] = "Hello"
		assert_is(type(put.exception), RuntimeError)
		assert_is(type(write.exception), RuntimeError)


def test_outer_middleware_cannot_write_to_the_flash():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
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

		handle(path, index, outer)

		assert_eq([type(error) for error in errors], [RuntimeError])


def test_outer_middleware_cannot_rotate_the_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
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

		handle(path, index, outer)

		assert_eq([type(error) for error in errors], [RuntimeError])
