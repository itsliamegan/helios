from uuid import uuid4

from lux.session import decode, encode, Session, Sessions

def test_finds_session_by_id():
	id = uuid4()
	session = Session(id)
	sessions = Sessions()

	sessions.put(session)

	assert sessions.get(id) == session

def test_stores_values():
	id = uuid4()
	session = Session(id)

	session["message"] = "You do not have access."

	assert session["message"] == "You do not have access."

def test_clears_values():
	id = uuid4()
	session = Session(id)
	session["user_id"] = "275544aa-5d0d-4c0f-969a-a4ebca010818"

	session.clear()

	assert "user_id" not in session

def test_deletes_values():
	id = uuid4()
	session = Session(id)
	session["user_id"] = "275544aa-5d0d-4c0f-969a-a4ebca010818"

	del session["user_id"]

	assert "user_id" not in session

def test_encodes_and_decodes_sessions():
	id = uuid4()
	session = Session(id)
	session["message"] = "You do not have access."
	sessions = Sessions({id: session})

	encoded = encode(sessions)
	decoded = decode(encoded)

	assert decoded.get(id)["message"] == "You do not have access."
