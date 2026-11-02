from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_is,
	assert_not_in,
	assert_raises,
)

from helios.session.session import Session


def test_mapping_clear_and_delete():
	session = Session("visitor-token")
	session["message"] = "Hello"
	assert_eq(session["message"], "Hello")

	del session["message"]
	assert_not_in("message", session)
	session["message"] = "Again"
	session.clear()
	assert_not_in("message", session)


def test_closed_session_refuses_setting_items():
	session = Session("visitor-token")
	session.close()

	with assert_raises(RuntimeError) as raised:
		session["message"] = "Hello"
	assert_is(type(raised.exception), RuntimeError)


def test_closed_session_refuses_deleting_items():
	session = Session("visitor-token", {"message": "Hello"})
	session.close()

	with assert_raises(RuntimeError) as raised:
		del session["message"]
	assert_is(type(raised.exception), RuntimeError)


def test_closed_session_refuses_clearing():
	session = Session("visitor-token", {"message": "Hello"})
	session.close()

	with assert_raises(RuntimeError) as raised:
		session.clear()
	assert_is(type(raised.exception), RuntimeError)


def test_closed_session_refuses_touching():
	session = Session("visitor-token")
	session.close()

	with assert_raises(RuntimeError) as raised:
		session.touch()
	assert_is(type(raised.exception), RuntimeError)


def test_closed_session_still_reads():
	session = Session("visitor-token", {"message": "Hello"})
	session.close()

	assert_eq(session["message"], "Hello")
	assert_in("message", session)
