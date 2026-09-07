from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.session import Session, Sessions, decode, encode


def test_finds_session_by_id():
	id = uuid4()
	session = Session(id)
	sessions = Sessions()

	sessions.put(session)

	assert_eq(sessions.get(id), session)


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


def test_encodes_and_decodes_sessions():
	id = uuid4()
	session = Session(id)
	session["message"] = "You do not have access."
	sessions = Sessions({id: session})

	encoded = encode(sessions)
	decoded = decode(encoded)

	assert_eq(decoded.get(id)["message"], "You do not have access.")
