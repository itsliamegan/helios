from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that
import time_machine

from helios.app import Application, Container, Provider
from helios.app import Config as AppConfig
from helios.http import Headers, Input, Method, Request, Response, URL
import helios.persist.config
from helios.persist.files import Files, Persistence
from helios.routing import Pattern, Route, Router
import helios.session
from helios.session.config import Config
from helios.session.store import MAX_AGE, Session, Sessions
from test.support import MemoryPersistence


def request(session_id: str | None = None) -> Request:
	headers = Headers()
	if session_id is not None:
		headers["Cookie"] = f"session_id={session_id}"
	return Request(Method.GET, URL("/"), headers, Input())


class PersistenceProvider(Provider):
	def __init__(self, persistence: MemoryPersistence):
		self.persistence = persistence

	def register(self, container: Container):
		container.scoped(Persistence, lambda context: self.persistence)


def exercise(
	sessions: Sessions,
	request: Request,
	change=None,
	secure: bool = False,
	resolve: bool = True,
):
	files = Files(helios.persist.config.Config(Path("persistence.lock")))
	persistence = MemoryPersistence(sessions)
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
			PersistenceProvider(persistence),
			helios.session.Provider(
				Config(Path("sessions.json"), secure=secure), files
			),
		],
	)
	response = app.handle(request)
	return (seen[0] if seen else None), response, persistence


def test_doesnt_load_or_persist_unused_session():
	sessions = Sessions()
	_, response, persistence = exercise(sessions, request(), resolve=False)

	assert_that("session_id" not in response.cookies)
	assert_that(persistence.handle.saved is None)


def test_doesnt_persist_empty_session():
	sessions = Sessions()
	session, response, persistence = exercise(sessions, request())

	assert_that(session.id not in sessions)
	assert_that("session_id" not in response.cookies)
	assert_that(persistence.handle.saved is None)


def test_persists_session_after_storing_data():
	sessions = Sessions()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	with time_machine.travel(now, tick=False):
		session, response, persistence = exercise(
			sessions, request(), lambda session: session.__setitem__("message", "Hello")
		)

	assert_that(session.id in sessions)
	assert_eq(session.last_active_at, now)
	assert_eq(response.cookies["session_id"].val, str(session.id))
	assert_eq(persistence.handle.saved, sessions)


def test_replaces_malformed_and_unknown_cookies():
	sessions = Sessions()
	malformed, _, _ = exercise(sessions, request("not-a-uuid"))
	unknown_id = uuid4()
	unknown, _, _ = exercise(sessions, request(str(unknown_id)))

	assert_that(malformed.id not in sessions)
	assert_that(unknown.id != unknown_id)
	assert_that(unknown_id not in sessions)


def test_reuses_known_session():
	id = uuid4()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	existing = Session(id, {"message": "Hello"})
	sessions = Sessions({id: existing})
	with time_machine.travel(now, tick=False):
		session, _, _ = exercise(sessions, request(str(id)))

	assert_that(session is existing)
	assert_eq(session.last_active_at, now)


def test_renews_session_at_expiry_boundary():
	id = uuid4()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	existing = Session(id, {"message": "Hello"}, last_active_at=now - MAX_AGE)
	with time_machine.travel(now, tick=False):
		session, _, _ = exercise(Sessions({id: existing}), request(str(id)))

	assert_that(session is existing)
	assert_eq(session.last_active_at, now)


def test_removes_expired_sessions():
	now = datetime(2026, 10, 12, tzinfo=UTC)
	active = Session(uuid4(), {"message": "Hello"}, last_active_at=now)
	expired = Session(
		uuid4(),
		last_active_at=now - MAX_AGE - timedelta(microseconds=1),
	)
	sessions = Sessions({active.id: active, expired.id: expired})
	with time_machine.travel(now, tick=False):
		session, _, persistence = exercise(sessions, request(str(active.id)))

	assert_that(session is active)
	assert_that(expired.id not in sessions)
	assert_eq(persistence.handle.saved, sessions)


def test_removes_session_after_its_data_is_cleared():
	session = Session(uuid4(), {"message": "Hello"})
	sessions = Sessions({session.id: session})
	provided, response, persistence = exercise(
		sessions, request(str(session.id)), lambda session: session.clear()
	)

	assert_that(provided.id not in sessions)
	assert_eq(response.cookies["session_id"].val, "")
	assert_eq(response.cookies["session_id"].expires, datetime(1970, 1, 1, tzinfo=UTC))
	assert_eq(persistence.handle.saved, sessions)


def test_doesnt_restore_invalidated_session():
	session = Session(uuid4(), {"message": "Hello"})
	sessions = Sessions({session.id: session})
	provided, response, persistence = exercise(
		sessions, request(str(session.id)), lambda session: session.invalidate()
	)

	assert_that(provided.id not in sessions)
	assert_eq(response.cookies["session_id"].val, "")
	assert_eq(persistence.handle.saved, sessions)


def test_sets_cookie_policy():
	session, response, _ = exercise(
		Sessions(),
		request(),
		lambda session: session.__setitem__("message", "Hello"),
		secure=True,
	)

	cookie = response.cookies["session_id"]
	assert_eq(cookie.val, str(session.id))
	assert_that(cookie.http_only)
	assert_that(cookie.secure)
	assert_eq(cookie.same_site, "Lax")
	assert_that(cookie.expires is not None)


def test_rotates_session():
	old_id = uuid4()
	session = Session(old_id, {"message": "Hello"})
	sessions = Sessions({old_id: session})
	provided, response, persistence = exercise(
		sessions, request(str(old_id)), lambda session: session.rotate()
	)

	assert_that(provided.id != old_id)
	assert_that(old_id not in sessions)
	assert_that(provided.id in sessions)
	assert_eq(sessions.get(provided.id)["message"], "Hello")
	assert_eq(response.cookies["session_id"].val, str(provided.id))
	assert_eq(persistence.handle.saved, sessions)
