from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.session.store import Format, Session, Sessions


def test_finds_session_by_id():
	id = uuid4()
	session = Session(id)
	sessions = Sessions()

	sessions.put(session)

	assert_eq(sessions.get(id), session)


def test_tracks_added_sessions():
	sessions = Sessions()

	sessions.put(Session(uuid4()))

	assert_that(sessions.is_dirty())


def test_tracks_changed_sessions():
	set_session = Session(uuid4())
	deleted_session = Session(uuid4(), {"message": "Hello"})
	cleared_session = Session(uuid4(), {"message": "Hello"})

	set_session["message"] = "Hello"
	del deleted_session["message"]
	cleared_session.clear()

	assert_that(Sessions({set_session.id: set_session}).is_dirty())
	assert_that(Sessions({deleted_session.id: deleted_session}).is_dirty())
	assert_that(Sessions({cleared_session.id: cleared_session}).is_dirty())


def test_stores_values():
	id = uuid4()
	session = Session(id)

	session["message"] = "You do not have access."

	assert_eq(session["message"], "You do not have access.")


def test_clears_values():
	id = uuid4()
	session = Session(id)
	session["user_id"] = "275544aa-5d0d-4c0f-969a-a4ebca010818"

	session.clear()

	assert_that("user_id" not in session)


def test_deletes_values():
	id = uuid4()
	session = Session(id)
	session["user_id"] = "275544aa-5d0d-4c0f-969a-a4ebca010818"

	del session["user_id"]

	assert_that("user_id" not in session)


def test_rotates_attached_session():
	old_id = uuid4()
	session = Session(old_id, {"message": "Hello"})
	sessions = Sessions({old_id: session})

	session.rotate()

	assert_that(session.id != old_id)
	assert_that(old_id not in sessions)
	assert_that(session.id in sessions)
	assert_eq(sessions.get(session.id)["message"], "Hello")
	assert_that(sessions.is_dirty())


def test_doesnt_rotate_detached_session():
	old_id = uuid4()
	session = Session(old_id)
	sessions = Sessions({old_id: session})
	del sessions.sessions[old_id]

	session.rotate()

	assert_eq(session.id, old_id)
	assert_that(not session.dirty)
	assert_that(not sessions.is_dirty())


def test_round_trips_sessions():
	id = uuid4()
	session = Session(id)
	session["message"] = "You do not have access."
	sessions = Sessions({id: session})

	encoded = Format().encode(sessions)
	decoded = Format().decode(encoded)

	assert_eq(decoded.get(id)["message"], "You do not have access.")
