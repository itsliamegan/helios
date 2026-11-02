from datetime import UTC, datetime, timedelta

from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_not,
	assert_not_eq,
	assert_not_none,
	assert_raises,
	assert_that,
)
import time_machine

from helios.session.driver import memory
from helios.session.session import Session
from helios.session.sessions import Sessions

MAXIMUM_AGE = timedelta(days=30)
NOW = datetime(2026, 3, 15, tzinfo=UTC)


def test_finds_a_saved_session():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.save(Session("visitor-token", {"message": "Hello"}))

	found = sessions.find("visitor-token")

	assert_eq(assert_not_none(found)["message"], "Hello")


def test_finds_no_session_for_an_unknown_token():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)

	assert_is(sessions.find("unknown-token"), None)


def test_finds_a_session_active_at_the_maximum_age():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.save(Session("visitor-token", last_active_at=NOW - MAXIMUM_AGE))

	with time_machine.travel(NOW, tick=False):
		found = sessions.find("visitor-token")

	assert_not_none(found)


def test_finds_no_expired_session():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.save(
		Session(
			"visitor-token",
			last_active_at=NOW - MAXIMUM_AGE - timedelta(microseconds=1),
		)
	)

	with time_machine.travel(NOW, tick=False):
		found = sessions.find("visitor-token")

	assert_is(found, None)


def test_saving_marks_a_session_stored():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token")

	sessions.save(session)

	assert_that(session.stored)


def test_destroys_a_session():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token", {"message": "Hello"})
	sessions.save(session)

	sessions.destroy(session)

	assert_is(sessions.find("visitor-token"), None)
	assert_not(session.stored)


def test_rotates_a_stored_session():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token", {"message": "Hello"})
	sessions.save(session)

	sessions.rotate(session)

	assert_not_eq(session.token, "visitor-token")
	assert_is(sessions.find("visitor-token"), None)
	assert_is(sessions.find(session.token), None)
	assert_eq(session["message"], "Hello")
	assert_not(session.stored)
	assert_that(session.dirty)


def test_rotated_session_is_stored_under_its_new_token_once_saved():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token", {"message": "Hello"})
	sessions.save(session)
	sessions.rotate(session)

	sessions.save(session)

	assert_eq(assert_not_none(sessions.find(session.token))["message"], "Hello")


def test_purges_expired_sessions():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.save(
		Session(
			"expired-token",
			last_active_at=NOW - MAXIMUM_AGE - timedelta(microseconds=1),
		)
	)
	sessions.save(Session("active-token", last_active_at=NOW - MAXIMUM_AGE))

	with time_machine.travel(NOW, tick=False):
		sessions.purge()

	assert_is(sessions.driver.read("expired-token"), None)
	assert_not_none(sessions.driver.read("active-token"))


def test_closed_sessions_refuse_saving():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.save(Session("visitor-token"))
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_refuse_destroying():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token")
	sessions.save(session)
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.destroy(session)
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_refuse_rotating():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token")
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.rotate(session)
	assert_is(type(raised.exception), RuntimeError)


def test_closed_sessions_refuse_purging():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.close()

	with assert_raises(RuntimeError) as raised:
		sessions.purge()
	assert_is(type(raised.exception), RuntimeError)


def test_rotating_a_closed_session_is_refused():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	session = Session("visitor-token")
	session.close()

	with assert_raises(RuntimeError) as raised:
		sessions.rotate(session)
	assert_is(type(raised.exception), RuntimeError)
	assert_eq(session.token, "visitor-token")


def test_closed_sessions_still_find():
	sessions = Sessions(memory.Driver(), MAXIMUM_AGE)
	sessions.save(Session("visitor-token", {"message": "Hello"}))
	sessions.close()

	assert_eq(assert_not_none(sessions.find("visitor-token"))["message"], "Hello")
