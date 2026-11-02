from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq

import helios.app
import helios.auth
from helios.auth import Authenticator
from helios.auth.test import sign_in
import helios.database
from helios.database import Database, Model
import helios.database.provider
from helios.database.registry import Registry
from helios.http import Response
from helios.routing import Route, Router
import helios.session
from helios.session.command import SKELETON_FILE
from helios.session.driver import database
from helios.wsgi import Application
from helios.wsgi.test import TestClient


class User(Model):
	table = "users"

	name: str


def test_signs_a_user_in_for_the_next_request():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		try:
			connection.executescript(
				"""
				CREATE TABLE users (
					id TEXT PRIMARY KEY,
					created_at TEXT NOT NULL,
					name TEXT NOT NULL
				);
				"""
				+ SKELETON_FILE.read_text()
			)
		finally:
			connection.close()
		with Database(path, Registry([User])).store() as store:
			user = store.create(User, name="Alice")

		def index(request, context):
			return Response.text(context.get(Authenticator[User]).user.name)

		app = Application(
			helios.app.Config(),
			Router([Route.get("/", index)]),
			[
				helios.session.Provider(helios.session.Config(database.Config())),
				helios.database.provider.Provider(
					helios.database.Config(path),
					[User, database.Record],
				),
				helios.auth.Provider(User),
			],
		)
		app.boot()
		try:
			client = TestClient(app)
			sign_in(client, user)
			response = client.get("/")
		finally:
			app.close()

	assert_eq(response.text, "Alice")
