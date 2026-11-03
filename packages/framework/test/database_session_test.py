from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_not_none, assert_raises

import helios.app
import helios.auth
import helios.database
from helios.database import Database, Model, ModelError, Store
import helios.database.provider
from helios.database.registry import Registry
from helios.database.sqlite import Connection
from helios.http import Headers, Method, Request, Response, Status
from helios.routing import Route, Router
import helios.session
from helios.session import Session, Sessions
from helios.session.command import MIGRATION_FILE
from helios.session.driver import database
import helios.session.driver.database.items
import helios.session.driver.database.token
from helios.url import URL


class User(Model):
	table = "users"

	name: str


SCHEMA = f"""
CREATE TABLE users (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL
);

{MIGRATION_FILE.read_text()}
"""


def request(token: str | None = None) -> Request:
	headers = Headers()
	if token is not None:
		headers["Cookie"] = f"session_id={token}"
	return Request(Method.GET, URL("/"), headers)


def application(path: Path, action) -> helios.app.Application:
	registry = Registry()
	registry.model(User)
	registry.model(database.Record)
	app = helios.app.Application(
		helios.app.Config(),
		Router([Route.get("/", action)]),
		[
			helios.session.Provider(helios.session.Config(database.Config())),
			helios.database.provider.Provider(helios.database.Config(path), registry),
			helios.auth.Provider(User),
		],
	)
	app.boot()
	return app


def create_database(path: Path):
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.executescript(SCHEMA)
	finally:
		connection.close()


def store_session(path: Path, session: Session):
	registry = Registry()
	registry.model(database.Record)
	registry.codec(helios.session.driver.database.token.Codec())
	registry.codec(helios.session.driver.database.items.Codec())
	with Database(path, registry).store() as store:
		database.Driver(store).write(session)


def read_session(path: Path, token: str) -> Session | None:
	registry = Registry()
	registry.model(database.Record)
	registry.codec(helios.session.driver.database.token.Codec())
	registry.codec(helios.session.driver.database.items.Codec())
	with Database(path, registry).store() as store:
		return database.Driver(store).read(token)


def user_names(path: Path) -> list[str]:
	connection = sqlite3.connect(path)
	try:
		return [
			row[0] for row in connection.execute("SELECT name FROM users ORDER BY name")
		]
	finally:
		connection.close()


def test_session_and_domain_writes_commit_together():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)

		def sign_in(request, context):
			store = context.get(Store)
			authenticator = context.get(helios.auth.Authenticator)
			user = store.create(User, name="Alice")
			authenticator.sign_in(user)
			return Response.empty(Status.OK)

		app = application(path, sign_in)
		try:
			response = app.handle(request())
		finally:
			app.close()

		token = response.cookies["session_id"].value
		assert_eq(user_names(path), ["Alice"])
		assert_not_none(read_session(path, token))


def test_session_and_domain_writes_roll_back_together():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		store_session(path, Session("visitor-token", {"message": "Before"}))

		def fail(request, context):
			store = context.get(Store)
			session = context.get(Session)
			store.create(User, name="Rolled back")
			session["message"] = "After"
			raise RuntimeError("failure")

		app = application(path, fail)
		try:
			response = app.handle(request("visitor-token"))
		finally:
			app.close()

		session = assert_not_none(read_session(path, "visitor-token"))
		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(user_names(path), [])
		assert_eq(session["message"], "Before")


def test_failed_request_rolls_back_a_rotation():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		store_session(path, Session("visitor-token", {"message": "Hello"}))

		def fail(request, context):
			sessions = context.get(Sessions)
			session = context.get(Session)
			sessions.rotate(session)
			raise RuntimeError("failure")

		app = application(path, fail)
		try:
			app.handle(request("visitor-token"))
		finally:
			app.close()

		session = assert_not_none(read_session(path, "visitor-token"))
		assert_eq(session["message"], "Hello")


def test_request_without_a_cookie_takes_no_write_lock():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)

		def index(request, context):
			context.get(helios.auth.Authenticator)
			return Response.empty(Status.OK)

		registry = Registry()
		registry.model(User)
		registry.model(database.Record)
		app = helios.app.Application(
			helios.app.Config(),
			Router([Route.get("/", index)]),
			[
				helios.session.Provider(helios.session.Config(database.Config())),
				helios.database.provider.Provider(
					helios.database.Config(path, busy_timeout=timedelta(0)),
					registry,
				),
				helios.auth.Provider(User),
			],
		)
		app.boot()
		lock = Connection.open(path)
		try:
			lock.begin()
			response = app.handle(request())
		finally:
			lock.close()
			app.close()

		assert_eq(response.status, Status.OK)


def test_boot_refuses_an_unregistered_session_model():
	with TemporaryDirectory() as directory:
		registry = Registry()
		registry.model(User)
		app = helios.app.Application(
			helios.app.Config(),
			Router([]),
			[
				helios.session.Provider(helios.session.Config(database.Config())),
				helios.database.provider.Provider(
					helios.database.Config(Path(directory, "app.sqlite")),
					registry,
				),
			],
		)

		with assert_raises(ModelError):
			app.boot()
