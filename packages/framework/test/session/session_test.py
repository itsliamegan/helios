from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not_in

from helios.session.session import Session


def test_mapping_clear_and_delete():
	session = Session(uuid4())
	session["message"] = "Hello"
	assert_eq(session["message"], "Hello")

	del session["message"]
	assert_not_in("message", session)
	session["message"] = "Again"
	session.clear()
	assert_not_in("message", session)
