from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not, assert_that

from helios.app import Application, Config, Container, Provider
import helios.auth
from helios.auth import Authenticator
from helios.data.model import Model, attr
from helios.data.store import Store
from helios.http import Headers, Input, Method, Request, Response, URL
from helios.routing import Pattern, Route, Router
from helios.session.store import Session


class User(Model):
	name = attr(str)


class Values(Provider):
	def __init__(self, store: Store, session: Session):
		self.store = store
		self.session = session

	def register(self, container: Container):
		container.scoped(Store, lambda context: self.store)
		container.scoped(Session, lambda context: self.session)


def resolve(store: Store, session: Session) -> Authenticator:
	resolved = []

	def index(request, context):
		resolved.append(context.get(Authenticator))
		return Response.empty()

	app = Application(
		Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[Values(store, session), helios.auth.Provider(User)],
	)
	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))
	return resolved[0]


def test_finds_no_user():
	provided = resolve(Store(), Session(uuid4()))

	assert_that(provided.user is None)
	assert_not(provided.is_signed_in())


def test_finds_user_from_session():
	store = Store()
	user = store.create(User, name="Alice")
	session = Session(uuid4())
	session["_user_id"] = str(user.id)

	provided = resolve(store, session)

	assert_eq(provided.user, user)
	assert_that(provided.is_signed_in())


def test_removes_stale_user_id():
	session = Session(uuid4())
	session["_user_id"] = str(uuid4())

	provided = resolve(Store(), session)

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)


def test_removes_malformed_user_id():
	session = Session(uuid4())
	session["_user_id"] = "not-a-uuid"

	provided = resolve(Store(), session)

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)
