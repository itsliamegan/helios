from datetime import UTC, datetime, timedelta
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that
import time_machine

from helios.session.store import Session, Store

MAXIMUM_AGE = timedelta(days=30)


def test_finds_session_by_id():
	id = uuid4()
	session = Session(id)
	store = Store()

	store.put(session)

	assert_eq(store.get(id), session)


def test_tracks_added_and_changed_sessions():
	store = Store()
	session = Session(uuid4())
	store.put(session)
	assert_that(store.is_dirty())

	changed = Session(uuid4())
	changed["message"] = "Hello"
	assert_that(Store({changed.id: changed}).is_dirty())


def test_mapping_clear_and_delete():
	session = Session(uuid4())
	session["message"] = "Hello"
	assert_eq(session["message"], "Hello")

	del session["message"]
	assert_that("message" not in session)
	session["message"] = "Again"
	session.clear()
	assert_that("message" not in session)


def test_rotates_attached_session_preserving_values():
	old_id = uuid4()
	session = Session(old_id, {"message": "Hello"})
	store = Store({old_id: session})

	session.rotate()

	assert_that(session.id != old_id)
	assert_that(old_id not in store)
	assert_that(session.id in store)
	assert_eq(store.get(session.id)["message"], "Hello")


def test_invalidates_attached_session():
	session = Session(uuid4())
	store = Store({session.id: session})

	session.invalidate()

	assert_that(session.id not in store)
	assert_that(store.is_dirty())


def test_purges_sessions_using_configured_maximum_age():
	now = datetime(2026, 3, 15, tzinfo=UTC)
	expired = Session(
		uuid4(), last_active_at=now - MAXIMUM_AGE - timedelta(microseconds=1)
	)
	active = Session(uuid4(), last_active_at=now - MAXIMUM_AGE)
	store = Store({expired.id: expired, active.id: active})

	with time_machine.travel(now, tick=False):
		store.purge(MAXIMUM_AGE)

	assert_that(expired.id not in store)
	assert_that(active.id in store)


def test_does_not_rotate_detached_session():
	old_id = uuid4()
	session = Session(old_id)
	store = Store({old_id: session})
	store.remove(old_id)

	session.rotate()

	assert_that(session.id != old_id)
	assert_that(session.id not in store)
