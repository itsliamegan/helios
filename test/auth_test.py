from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not, assert_that

from helios.app import Context
from helios.auth import Authenticator, Component
from helios.http import Headers, Input, Method, Request, URL
from helios.session import Session
from helios.store import Model, Store, attr


class User(Model):
	name = attr(str)


def context(store: Store, session: Session) -> Context:
	ctx = Context()
	ctx.store = store
	ctx.session = session
	return ctx


def request() -> Request:
	return Request(Method.GET, URL("/"), Headers(), Input())


def test_finds_no_user_when_signed_out():
	ctx = context(Store(), Session(uuid4()))
	auth = Component(User)

	auth.before(request(), ctx)

	assert_that(ctx.auth.user is None)
	assert_not(ctx.auth.is_signed_in())


def test_finds_user_from_session():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	session["_user_id"] = str(user.id)
	ctx = context(store, session)
	auth = Component(User)

	auth.before(request(), ctx)

	assert_eq(ctx.auth.user, user)
	assert_that(ctx.auth.is_signed_in())


def test_finds_no_user_when_session_is_stale():
	session = Session(uuid4())
	session["_user_id"] = str(uuid4())
	ctx = context(Store(), session)
	auth = Component(User)

	auth.before(request(), ctx)

	assert_that(ctx.auth.user is None)


def test_signs_in():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	auth = Authenticator(session)

	auth.sign_in(user)

	assert_eq(auth.user, user)
	assert_eq(session["_user_id"], str(user.id))


def test_signs_out():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	auth = Authenticator(session, user)

	auth.sign_out()

	assert_that(auth.user is None)
	assert_that("_user_id" not in session)


def test_signs_out_when_already_signed_out():
	auth = Authenticator(Session(uuid4()))

	auth.sign_out()

	assert_that(auth.user is None)


def test_keeps_other_session_values_on_sign_out():
	session = Session(uuid4())
	session["_flash"] = {"message": "Signed out."}
	auth = Authenticator(session)

	auth.sign_out()

	assert_that("_flash" in session)


def test_uses_a_configurable_session_key():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	session["current_user"] = str(user.id)
	ctx = context(store, session)

	Component(User, "current_user").before(request(), ctx)

	assert_eq(ctx.auth.user, user)
