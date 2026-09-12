from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

import helios.app
from helios.app import Application, ComponentError, Context
from helios.data.component import Component
from helios.data.config import Config
from helios.data.model import Model, attr
from helios.data.store import Format, Schema, Store
from helios.http import Headers, Input, Method, Request, Response, Status, URL
import helios.persist.component
import helios.persist.config
from helios.persist.files import Files, JSONFile, Persistence
from helios.routing import NotFoundError, Pattern, Route, Router
from test.support import MemoryPersistence


class Post(Model):
	title = attr(str)


def request() -> Request:
	return Request(Method.GET, URL("/"), Headers(), Input())


def persistence(path: Path) -> tuple[Files, JSONFile[Store]]:
	files = Files(helios.persist.config.Config(Path(path.parent, "persistence.lock")))
	file = files.json(path, Format(Schema([Post])))
	return files, file


def application(path: Path, handler) -> Application:
	files, _ = persistence(path)
	return Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), handler)]),
		[
			helios.persist.component.Component(files),
			Component(Config(path), files, Schema([Post])),
		],
	)


def load_store(path: Path) -> Store:
	files, file = persistence(path)
	with files.lock() as scope:
		return scope.open(file).load()


def test_uses_persistence_protocol():
	persistence = MemoryPersistence(Store())
	files = Files(helios.persist.config.Config(Path("persistence.lock")))
	component = Component(Config(Path("store.json")), files, Schema([Post]))
	ctx = Context()
	ctx.put(Persistence, persistence)

	store = component.provide(ctx)
	ctx.put(Store, store)
	store.create(Post, title="Intro")
	component.finish(Response.empty(), ctx)

	assert_eq(persistence.handle.saved, store)


def test_skips_write_for_unchanged_store():
	def index(req, ctx):
		ctx.get(Store).find_all(Post)
		return Response.empty(Status.OK)

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]\n")
		app = application(path, index)

		app.handle(request())

		assert_eq(path.read_text(), "[]\n")


def test_requires_persistence():
	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		files, _ = persistence(path)
		component = Component(Config(path), files, Schema([Post]))

		with assert_raises(ComponentError):
			component.provide(Context())


def test_redirect_saves():
	def create(req, ctx):
		ctx.get(Store).create(Post, title="Intro")
		return Response.redirect(URL("/posts"))

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load_store(path)

		assert_eq(res.status, Status.FOUND)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_http_error_saves():
	def create(req, ctx):
		ctx.get(Store).create(Post, title="Intro")
		raise NotFoundError()

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load_store(path)

		assert_eq(res.status, Status.NOT_FOUND)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_returned_error_saves():
	def create(req, ctx):
		ctx.get(Store).create(Post, title="Intro")
		return Response.text("Failed", Status.INTERNAL_SERVER_ERROR)

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load_store(path)

		assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(persisted.find_all(Post)[0].title, "Intro")


def test_exception_skips_save():
	def create(req, ctx):
		ctx.get(Store).create(Post, title="Intro")
		raise RuntimeError

	with TemporaryDirectory() as dir:
		path = Path(dir, "store.json")
		path.write_text("[]")
		app = application(path, create)

		res = app.handle(request())
		persisted = load_store(path)

		assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)
		assert_eq(persisted.find_all(Post), [])
