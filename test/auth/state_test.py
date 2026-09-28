from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not, assert_raises, assert_that

from helios.auth import AuthenticationError, Authenticator
from helios.database import Model
from helios.session.store import Session, Store


class User(Model):
	table = "users"

	name: str


def test_signs_in():
	user = User(name="Alice")
	session = Session(uuid4())
	sessions = Store({session.id: session})
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
	sessions = Store({session.id: session})
	old_id = session.id
	auth = Authenticator(session, user)

	auth.sign_out()

	assert_that(session.id != old_id)
	assert_that(old_id not in sessions)
	assert_not(auth.is_signed_in())
	assert_that("_user_id" not in session)


def test_signs_out_when_already_signed_out():
	session = Session(uuid4())
	old_id = session.id
	auth = Authenticator(session)

	auth.sign_out()

	assert_that(session.id != old_id)
	assert_not(auth.is_signed_in())


def test_keeps_other_session_values_on_sign_out():
	session = Session(uuid4())
	session["_flash"] = {"message": "Signed out."}
	auth = Authenticator(session)

	auth.sign_out()

	assert_that("_flash" in session)


def test_returns_user_when_signed_in():
	user = User(name="Alice")
	auth = Authenticator(Session(uuid4()), user)

	assert_eq(auth.user, user)


def test_rejects_user_when_signed_out():
	auth = Authenticator(Session(uuid4()))

	with assert_raises(AuthenticationError) as raised:
		_ = auth.user

	assert_eq(str(raised.exception), "no user is signed in")
