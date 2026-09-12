from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that
import time_machine

from helios.app import Context
from helios.http import Headers, Input, Method, Request, Response, URL
import helios.persist.config
from helios.persist.files import Files, Persistence
from helios.session.component import Component
from helios.session.config import Config
from helios.session.store import MAX_AGE, Session, Sessions
from test.support import MemoryPersistence


def request(session_id: str | None = None) -> Request:
	headers = Headers()
	if session_id is not None:
		headers["Cookie"] = f"session_id={session_id}"
	return Request(Method.GET, URL("/"), headers, Input())


def setup(sessions: Sessions, *, secure: bool = False):
	files = Files(helios.persist.config.Config(Path("persistence.lock")))
	component = Component(
		Config(Path("sessions.json"), secure=secure),
		files,
	)
	persistence = MemoryPersistence(sessions)
	ctx = Context()
	ctx.put(Persistence, persistence)
	return component, persistence, ctx


def test_generates_id_without_cookie():
	sessions = Sessions()
	component, persistence, ctx = setup(sessions)

	session = component.provide(request(), ctx)
	ctx.put(Session, session)
	component.finish(Response.empty(), ctx)

	assert_that(session.id in sessions)
	assert_eq(persistence.handle.saved, sessions)


def test_replaces_malformed_cookie_id():
	sessions = Sessions()
	component, _, ctx = setup(sessions)

	session = component.provide(request("not-a-uuid"), ctx)

	assert_that(session.id in sessions)


def test_replaces_unknown_cookie_id():
	unknown_id = uuid4()
	sessions = Sessions()
	component, _, ctx = setup(sessions)

	session = component.provide(request(str(unknown_id)), ctx)

	assert_that(session.id != unknown_id)
	assert_that(unknown_id not in sessions)
	assert_that(session.id in sessions)


def test_reuses_known_session():
	id = uuid4()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	existing = Session(id, {"message": "Hello"})
	sessions = Sessions({id: existing})
	component, _, ctx = setup(sessions)

	with time_machine.travel(now, tick=False):
		session = component.provide(request(str(id)), ctx)

	assert_that(session is existing)
	assert_eq(session.id, id)
	assert_eq(session.last_active_at, now)


def test_renews_session_at_expiry_boundary():
	id = uuid4()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	existing = Session(id, last_active_at=now - MAX_AGE)
	sessions = Sessions({id: existing})
	component, _, ctx = setup(sessions)

	with time_machine.travel(now, tick=False):
		session = component.provide(request(str(id)), ctx)

	assert_that(session is existing)
	assert_eq(session.last_active_at, now)


def test_removes_expired_session():
	id = uuid4()
	now = datetime(2026, 10, 12, tzinfo=UTC)
	existing = Session(
		id,
		{"message": "Hello"},
		last_active_at=now - MAX_AGE - timedelta(microseconds=1),
	)
	sessions = Sessions({id: existing})
	component, _, ctx = setup(sessions)

	with time_machine.travel(now, tick=False):
		session = component.provide(request(str(id)), ctx)

	assert_that(session.id != id)
	assert_that(id not in sessions)
	assert_that(session.id in sessions)


def test_sets_cookie_policy():
	sessions = Sessions()
	component, _, ctx = setup(sessions, secure=True)
	session = component.provide(request(), ctx)
	ctx.put(Session, session)
	response = Response.empty()

	component.finish(response, ctx)

	cookie = response.cookies["session_id"]
	assert_that(cookie.http_only)
	assert_that(cookie.secure)
	assert_eq(cookie.same_site, "Lax")
	assert_that(cookie.expires is not None)


def test_rotates_session():
	old_id = uuid4()
	session = Session(old_id, {"message": "Hello"})
	sessions = Sessions({old_id: session})
	component, persistence, ctx = setup(sessions)
	provided = component.provide(request(str(old_id)), ctx)
	ctx.put(Session, provided)

	provided.rotate()
	response = Response.empty()
	component.finish(response, ctx)

	assert_that(provided.id != old_id)
	assert_that(old_id not in sessions)
	assert_that(provided.id in sessions)
	assert_eq(sessions.get(provided.id)["message"], "Hello")
	assert_eq(response.cookies["session_id"].val, str(provided.id))
	assert_eq(persistence.handle.saved, sessions)
