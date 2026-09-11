from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not, assert_that

from helios.app import Context
from helios.auth.component import Component
from helios.data.model import Model, attr
from helios.data.store import Store
from helios.http import Headers, Input, Method, Request, URL
from helios.session.store import Session


class User(Model):
	name = attr(str)


def context(store: Store, session: Session) -> Context:
	ctx = Context()
	ctx.put(Store, store)
	ctx.put(Session, session)
	return ctx


def request() -> Request:
	return Request(Method.GET, URL("/"), Headers(), Input())


def test_finds_no_user():
	ctx = context(Store(), Session(uuid4()))
	auth = Component(User)

	provided = auth.provide(request(), ctx)

	assert_that(provided.user is None)
	assert_not(provided.is_signed_in())


def test_finds_user_from_session():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	session["_user_id"] = str(user.id)
	ctx = context(store, session)
	auth = Component(User)

	provided = auth.provide(request(), ctx)

	assert_eq(provided.user, user)
	assert_that(provided.is_signed_in())


def test_removes_stale_user_id():
	session = Session(uuid4())
	session["_user_id"] = str(uuid4())
	ctx = context(Store(), session)
	auth = Component(User)

	provided = auth.provide(request(), ctx)

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)


def test_removes_malformed_user_id():
	session = Session(uuid4())
	session["_user_id"] = "not-a-uuid"
	ctx = context(Store(), session)
	auth = Component(User)

	provided = auth.provide(request(), ctx)

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)
