from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_that

import helios.app
from helios.app import Application
from helios.database import Config, Model, Provider, Store
from helios.http import Method, Request, Response, Status, URL
from helios.http.error import NotFoundError
from helios.routing import Route, Router


class Post(Model):
	table = "posts"

	title: str


class Child(Model):
	table = "children"

	parent_id: str


def request() -> Request:
	return Request(Method.GET, URL("/"))


def application(path: Path, handler, model_types=None) -> Application:
	return Application(
		helios.app.Config(),
		Router([Route.get("/", handler)]),
		[Provider(Config(path), model_types or [Post])],
	)


def create_schema(path: Path, schema: str = ""):
	if not schema:
		schema = """
		CREATE TABLE posts (
			id TEXT PRIMARY KEY,
			created_at TEXT NOT NULL,
			title TEXT NOT NULL
		)
		"""
	connection = sqlite3.connect(path, autocommit=True)
	connection.executescript(schema)
	connection.close()


def titles(path: Path) -> list[str]:
	connection = sqlite3.connect(path)
	try:
		return [row[0] for row in connection.execute("SELECT title FROM posts")]
	finally:
		connection.close()


def test_unused_provider_does_not_touch_database_target():
	with TemporaryDirectory() as directory:
		path = Path(directory, "missing", "app.sqlite")
		app = application(path, lambda request, context: Response.empty(Status.OK))
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.OK)
		assert_that(not path.exists())


def test_normal_and_redirect_responses_commit():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(path)

		def create(request, context):
			context.get(Store).create(Post, title="Intro")
			return Response.redirect(URL("/posts"))

		app = application(path, create)
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.FOUND)
		assert_eq(titles(path), ["Intro"])


def test_raised_http_error_rolls_back():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(path)

		def missing(request, context):
			context.get(Store).create(Post, title="Rolled back")
			raise NotFoundError()

		app = application(path, missing)
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.NOT_FOUND)
		assert_eq(titles(path), [])


def test_returned_error_response_commits():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(path)

		def returned(request, context):
			context.get(Store).create(Post, title="Returned")
			return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

		app = application(path, returned)
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(titles(path), ["Returned"])


def test_unexpected_exception_rolls_back_and_next_request_can_use_database():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(path)

		def fail(request, context):
			context.get(Store).create(Post, title="Rolled back")
			raise RuntimeError("failure")

		app = application(path, fail)
		try:
			response = app.handle(request())
		finally:
			app.close()
		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(titles(path), [])

		def succeed(request, context):
			context.get(Store).create(Post, title="Committed")
			return Response.empty(Status.OK)

		app = application(path, succeed)
		try:
			response = app.handle(request())
		finally:
			app.close()
		assert_eq(response.status, Status.OK)
		assert_eq(titles(path), ["Committed"])


def test_request_shares_transaction():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(path)

		def create(request, context):
			store = context.get(Store)
			post = store.create(Post, title="Intro")
			store.update(post, title="Revised")
			assert_eq(store.find_one(Post, post.id).title, "Revised")
			return Response.empty(Status.OK)

		app = application(path, create)
		try:
			response = app.handle(request())
		finally:
			app.close()

		assert_eq(response.status, Status.OK)
		assert_eq(titles(path), ["Revised"])


def test_commit_failure_returns_error_and_leaves_no_row():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_schema(
			path,
			"""
			CREATE TABLE parents (id TEXT PRIMARY KEY);
			CREATE TABLE children (
				id TEXT PRIMARY KEY,
				created_at TEXT NOT NULL,
				parent_id TEXT NOT NULL,
				FOREIGN KEY (parent_id) REFERENCES parents (id)
					DEFERRABLE INITIALLY DEFERRED
			);
			""",
		)

		def create(request, context):
			context.get(Store).create(Child, parent_id="missing")
			return Response.empty(Status.OK)

		app = application(path, create, [Child])
		try:
			response = app.handle(request())
		finally:
			app.close()

		connection = sqlite3.connect(path)
		try:
			count = connection.execute("SELECT COUNT(*) FROM children").fetchone()
		finally:
			connection.close()
		assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(count, (0,))
