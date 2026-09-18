from datetime import UTC, datetime, timedelta
import json
import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that
import time_machine

from helios.app import Application
from helios.app import Config as AppConfig
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import NotFoundError, Pattern, Route, Router
import helios.session
from helios.session.file import Driver
from helios.session.store import Session

MAXIMUM_AGE = timedelta(days=30)


def request(session_id: str | None = None) -> Request:
	headers = Headers()
	if session_id is not None:
		headers["Cookie"] = f"session_id={session_id}"
	return Request(Method.GET, URL("/"), headers, Input())


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
				change(session)
		return Response.empty()

	app = Application(
		AppConfig(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[
			helios.session.Provider(
				helios.session.Config(secure=secure, maximum_age=maximum_age),
				Driver(path, path.with_suffix(".lock")),
			)
		],
	)
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

		assert_that("session_id" not in unused_response.cookies)
		assert_that("session_id" not in empty_response.cookies)
		assert_that(empty is not None)
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
				lambda session: session.__setitem__("message", "Hello"),
				secure=True,
			)

		stored = read_sessions(path)
		cookie = response.cookies["session_id"]
		assert_eq(stored[str(session.id)]["items"], {"message": "Hello"})
		assert_eq(cookie.val, str(session.id))
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
				path, request(str(old_id)), lambda session: session.rotate()
			)

		stored = read_sessions(path)
		assert_that(session.id != old_id)
		assert_that(str(old_id) not in stored)
		assert_eq(stored[str(session.id)]["items"], {"message": "Hello"})
		assert_eq(stored[str(session.id)]["last_active_at"], now.isoformat())
		assert_eq(response.cookies["session_id"].val, str(session.id))


def test_replaces_malformed_and_unknown_cookies():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)
		malformed, _ = exercise(path, request("not-a-uuid"))
		unknown_id = uuid4()
		unknown, _ = exercise(path, request(str(unknown_id)))

		assert_that(malformed.id != unknown_id)
		assert_that(unknown.id != unknown_id)
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
		assert_that(str(expired_id) not in stored)


def test_clear_and_invalidate_remove_persisted_session():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		first_id = uuid4()
		write_sessions(path, {str(first_id): session_data({"message": "Hello"})})
		_, response = exercise(
			path, request(str(first_id)), lambda session: session.clear()
		)
		assert_eq(read_sessions(path), {})
		assert_eq(response.cookies["session_id"].val, "")
		assert_eq(
			response.cookies["session_id"].expires, datetime(1970, 1, 1, tzinfo=UTC)
		)

		second_id = uuid4()
		write_sessions(path, {str(second_id): session_data({"message": "Hello"})})
		_, response = exercise(
			path, request(str(second_id)), lambda session: session.invalidate()
		)
		assert_eq(read_sessions(path), {})
		assert_eq(response.cookies["session_id"].val, "")


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
			Router([Route(Method.GET, Pattern("/"), fail)]),
			[helios.session.Provider(helios.session.Config(), driver)],
		)
		try:
			response = app.handle(request(str(id)))
		finally:
			app.close()

		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(read_sessions(path), initial)
		with driver.open() as store:
			assert_eq(store.get(id)["message"], "Before")


def test_handled_http_error_saves_mutation():
	with TemporaryDirectory() as directory:
		path = Path(directory, "sessions.json")
		write_sessions(path)

		def fail(request, context):
			context.get(Session)["message"] = "Saved"
			raise NotFoundError()

		app = Application(
			AppConfig(),
			Router([Route(Method.GET, Pattern("/"), fail)]),
			[
				helios.session.Provider(
					helios.session.Config(),
					Driver(path, path.with_suffix(".lock")),
				)
			],
		)
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.NOT_FOUND)
		assert_eq(
			next(iter(read_sessions(path).values()))["items"], {"message": "Saved"}
		)


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
