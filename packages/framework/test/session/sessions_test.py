from datetime import UTC, datetime, timedelta
from uuid import uuid4

from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_is,
	assert_not,
	assert_not_eq,
	assert_not_in,
	assert_raises,
	assert_that,
)
import time_machine

from helios.session.session import Session
from helios.session.sessions import Sessions

MAXIMUM_AGE = timedelta(days=30)


def test_finds_session_by_id():
	id = uuid4()
	session = Session(id)
	sessions = Sessions()

	sessions.put(session)

	assert_eq(sessions.get(id), session)


def test_tracks_added_and_changed_sessions():
	sessions = Sessions()
	session = Session(uuid4())
	sessions.put(session)
	assert_that(sessions.is_dirty())

	changed = Session(uuid4())
	changed["message"] = "Hello"
	assert_that(Sessions({changed.id: changed}).is_dirty())


def test_rotates_stored_session_preserving_values():
	old_id = uuid4()
	session = Session(old_id, {"message": "Hello"})
	sessions = Sessions({old_id: session})

	sessions.rotate(session)

	assert_not_eq(session.id, old_id)
	assert_not_in(old_id, sessions)
	assert_in(session.id, sessions)
	assert_eq(sessions.get(session.id)["message"], "Hello")


def test_rotates_unstored_session_without_storing_it():
	old_id = uuid4()
	session = Session(old_id)
	sessions = Sessions()

	sessions.rotate(session)

	assert_not_eq(session.id, old_id)
	assert_not_in(session.id, sessions)
	assert_not(sessions.is_dirty())


def test_rejects_rotating_a_session_whose_id_holds_another():
	id = uuid4()
	sessions = Sessions({id: Session(id)})

	with assert_raises(RuntimeError):
		sessions.rotate(Session(id))


def test_purges_sessions_using_configured_maximum_age():
	now = datetime(2026, 3, 15, tzinfo=UTC)
	expired = Session(
		uuid4(), last_active_at=now - MAXIMUM_AGE - timedelta(microseconds=1)
	)
	active = Session(uuid4(), last_active_at=now - MAXIMUM_AGE)
	sessions = Sessions({expired.id: expired, active.id: active})

	with time_machine.travel(now, tick=False):
		sessions.purge(MAXIMUM_AGE)

	assert_not_in(expired.id, sessions)
	assert_in(active.id, sessions)


def test_closed_sessions_refuse_putting():
	sessions = Sessions()
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.put(Session(uuid4()))
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_refuse_removing():
	id = uuid4()
	sessions = Sessions({id: Session(id)})
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.remove(id)
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_refuse_rotating():
	id = uuid4()
	session = Session(id)
	sessions = Sessions({id: session})
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.rotate(session)
	assert_is(type(raised.exception), RuntimeError)


def test_rotating_a_closed_session_is_refused():
	id = uuid4()
	session = Session(id)
	sessions = Sessions({id: session})
	session.close()

	with assert_raises(RuntimeError) as raised:
		sessions.rotate(session)
	assert_is(type(raised.exception), RuntimeError)
	assert_eq(session.id, id)


def test_closing_sessions_closes_their_sessions():
	id = uuid4()
	sessions = Sessions({id: Session(id)})
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.get(id)["message"] = "Hello"
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_still_read():
	id = uuid4()
	session = Session(id, {"message": "Hello"})
	sessions = Sessions({id: session})
	sessions.close()

	assert_is(sessions.get(id), session)
	assert_in(id, sessions)
	assert_not(sessions.is_dirty())
