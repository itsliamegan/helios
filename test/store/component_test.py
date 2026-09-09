from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq

from helios.app import Application
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import NotFoundError, Pattern, Route, Router
from helios.store import Component, Model, Schema, attr, load


class Post(Model):
	title = attr(str)


def request() -> Request:
	return Request(Method.GET, URL("/"), Headers(), Input())


def application(path: Path, handler) -> Application:
	return Application(
		Router([Route(Method.GET, Pattern("/"), handler)]),
		[Component(path, Schema([Post]))],
	)


def test_skips_read_only_write():
	def index(req, ctx):
		ctx.store.find_all(Post)
		return Response.empty(Status.OK)

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]\n")
		app = application(path, index)

		app.handle(request())

		assert_eq(path.read_text(), "[]\n")


def test_redirect_saves():
	def create(req, ctx):
		ctx.store.create(Post, title="Intro")
		return Response.redirect(URL("/posts"))

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load(path, Schema([Post]))

		assert_eq(res.status, Status.FOUND)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_http_error_saves():
	def create(req, ctx):
		ctx.store.create(Post, title="Intro")
		raise NotFoundError()

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load(path, Schema([Post]))

		assert_eq(res.status, Status.NOT_FOUND)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_returned_error_saves():
	def create(req, ctx):
		ctx.store.create(Post, title="Intro")
		return Response.text("Failed", Status.INTERNAL_SERVER_ERROR)

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load(path, Schema([Post]))

		assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_exception_skips_save():
	def create(req, ctx):
		ctx.store.create(Post, title="Intro")
		raise RuntimeError

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load(path, Schema([Post]))

		assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(persisted.find_all(Post), [])
