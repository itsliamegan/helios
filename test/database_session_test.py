import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_that

import helios.app
import helios.auth
import helios.database
from helios.database import Model, Store, attr
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import Pattern, Route, Router
import helios.session
from helios.session.file import Driver


class User(Model):
	table = "users"

	name = attr(str)


def request(session_id: str | None = None) -> Request:
	headers = Headers()
	if session_id is not None:
		headers["Cookie"] = f"session_id={session_id}"
	return Request(Method.GET, URL("/"), headers, Input())


def application(database_path: Path, session_path: Path, handler):
	return helios.app.Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), handler)]),
		[
			helios.session.Provider(
				helios.session.Config(),
				Driver(session_path, session_path.with_suffix(".lock")),
			),
			helios.database.Provider(
				helios.database.Config(database_path),
				[User],
			),
			helios.auth.Provider(User),
		],
	)


def user_names(path: Path) -> list[str]:
	connection = sqlite3.connect(path)
	try:
		return [
			row[0] for row in connection.execute("SELECT name FROM users ORDER BY name")
		]
	finally:
		connection.close()


def test_session_and_database_resources_persist_and_recover_together():
	with TemporaryDirectory() as directory:
		directory_path = Path(directory)
		database_path = directory_path / "app.sqlite"
		session_path = directory_path / "sessions.json"
		session_path.write_text("{}")
		connection = sqlite3.connect(database_path, autocommit=True)
		connection.execute(
			"""
			CREATE TABLE users (
				id TEXT PRIMARY KEY,
				created_at TEXT NOT NULL,
				name TEXT NOT NULL
			)
			"""
		)
		connection.close()

		def sign_in(request, context):
			authenticator = context.get(helios.auth.Authenticator)
			user = context.get(Store).create(User, name="Alice")
			authenticator.sign_in(user)
			return Response.empty(Status.OK)

		app = application(database_path, session_path, sign_in)
		try:
			response = app.handle(request())
		finally:
			app.close()
		session_id = response.cookies["session_id"].val
		assert_eq(user_names(database_path), ["Alice"])
		assert_that(json.loads(session_path.read_text())[session_id]["items"])

		before_failure = session_path.read_text()

		def fail(request, context):
			authenticator = context.get(helios.auth.Authenticator)
			assert_that(authenticator.is_signed_in())
			context.get(Store).create(User, name="Rolled back")
			authenticator.session["failure"] = True
			raise RuntimeError("failure")

		app = application(database_path, session_path, fail)
		try:
			response = app.handle(request(session_id))
		finally:
			app.close()
		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(user_names(database_path), ["Alice"])
		assert_eq(session_path.read_text(), before_failure)

		def recover(request, context):
			authenticator = context.get(helios.auth.Authenticator)
			assert_that(authenticator.is_signed_in())
			context.get(Store).create(User, name="Bob")
			authenticator.session["recovered"] = True
			return Response.empty(Status.OK)

		app = application(database_path, session_path, recover)
		try:
			response = app.handle(request(session_id))
		finally:
			app.close()
		assert_eq(response.status, Status.OK)
		assert_eq(user_names(database_path), ["Alice", "Bob"])
		assert_eq(
			json.loads(session_path.read_text())[session_id]["items"]["recovered"],
			True,
		)
