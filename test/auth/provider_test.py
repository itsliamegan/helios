from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_not, assert_that

from helios.app import Application, Config, Container, Provider
import helios.auth
from helios.auth import Authenticator
from helios.database import Config as DatabaseConfig
from helios.database import Model, Store, attr
from helios.database.sqlite import connect
from helios.http import Headers, Input, Method, Request, Response, URL
from helios.routing import Pattern, Route, Router
from helios.session.store import Session


class User(Model):
	table = "users"

	name = attr(str)


class Values(Provider):
	def __init__(self, store: Store, session: Session):
		self.store = store
		self.session = session

	def register(self, container: Container):
		container.scoped(Store, lambda context: self.store)
		container.scoped(Session, lambda context: self.session)


def create_store(path: Path):
	raw = sqlite3.connect(path, autocommit=True)
	raw.execute(
		"""
		CREATE TABLE users (
			id TEXT PRIMARY KEY,
			created_at TEXT NOT NULL,
			name TEXT NOT NULL
		)
		"""
	)
	raw.close()
	connection = connect(DatabaseConfig(path))
	connection.begin()
	return connection, Store(connection, [User])


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
	try:
		app.handle(Request(Method.GET, URL("/"), Headers(), Input()))
	finally:
		app.close()
	return resolved[0]


def test_finds_no_user():
	with TemporaryDirectory() as directory:
		connection, store = create_store(Path(directory) / "app.sqlite")
		try:
			provided = resolve(store, Session(uuid4()))
		finally:
			connection.close()

	assert_that(provided.user is None)
	assert_not(provided.is_signed_in())


def test_finds_user_from_session():
	with TemporaryDirectory() as directory:
		connection, store = create_store(Path(directory) / "app.sqlite")
		try:
			user = store.create(User, name="Alice")
			session = Session(uuid4())
			session["_user_id"] = str(user.id)

			provided = resolve(store, session)
		finally:
			connection.close()

	assert_eq(provided.user, user)
	assert_that(provided.is_signed_in())


def test_removes_stale_user_id():
	with TemporaryDirectory() as directory:
		connection, store = create_store(Path(directory) / "app.sqlite")
		try:
			session = Session(uuid4())
			session["_user_id"] = str(uuid4())
			provided = resolve(store, session)
		finally:
			connection.close()

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)


def test_removes_malformed_user_id():
	with TemporaryDirectory() as directory:
		connection, store = create_store(Path(directory) / "app.sqlite")
		try:
			session = Session(uuid4())
			session["_user_id"] = "not-a-uuid"
			provided = resolve(store, session)
		finally:
			connection.close()

	assert_that(provided.user is None)
	assert_that("_user_id" not in session)
