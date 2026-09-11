from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.auth.state import Authenticator
from helios.data.model import Model, attr
from helios.session.store import Session, Sessions


class User(Model):
	name = attr(str)


def test_signs_in():
	user = User(name="Alice")
	session = Session(uuid4())
	sessions = Sessions({session.id: session})
	old_id = session.id
	auth = Authenticator(session)

	auth.sign_in(user)

	assert_that(session.id != old_id)
	assert_that(old_id not in sessions)
	assert_eq(auth.user, user)
	assert_eq(session["_user_id"], str(user.id))


def test_signs_out():
	user = User(name="Alice")
	session = Session(uuid4())
	sessions = Sessions({session.id: session})
	old_id = session.id
	auth = Authenticator(session, user)

	auth.sign_out()

	assert_that(session.id != old_id)
	assert_that(old_id not in sessions)
	assert_that(auth.user is None)
	assert_that("_user_id" not in session)


def test_signs_out_when_already_signed_out():
	session = Session(uuid4())
	old_id = session.id
	auth = Authenticator(session)

	auth.sign_out()

	assert_that(session.id != old_id)
	assert_that(auth.user is None)


def test_keeps_other_session_values_on_sign_out():
	session = Session(uuid4())
	session["_flash"] = {"message": "Signed out."}
	auth = Authenticator(session)

	auth.sign_out()

	assert_that("_flash" in session)
