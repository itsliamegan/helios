from helios.app import Application, Component
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import Pattern, Route
from helios.store import Model, Store

from uuid import uuid4

def test_boots_components():
	class ExampleComponent(Component):
		def boot(self):
			self.booted = True

	component = ExampleComponent()
	app = Application([], [component])

	app.boot()

	assert component.booted == True

def test_ensures_content_length():
	def index(req, ctx):
		return Response.text("Hello, world!")

	app = Application([Route(Method.GET, Pattern("/"), index)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert str(res.headers["Content-Length"]) == "13"

def test_adapts_artificial_method():
	def destroy(req, ctx):
		return Response.empty()

	app = Application([Route(Method.DELETE, Pattern("/"), destroy)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input({"_method": "DELETE"}))

	res = app.handle(req)

	assert res.status == Status.NO_CONTENT

def test_captures_errors():
	def index(req, ctx):
		raise RuntimeError

	app = Application([Route(Method.GET, Pattern("/"), index)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.INTERNAL_SERVER_ERROR

def test_handles_route_not_found():
	app = Application([], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.NOT_FOUND

def test_handles_model_not_found():
	class Post(Model):
		pass

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	app = Application([Route(Method.GET, Pattern("/posts/missing"), show)], [])
	req = Request(Method.GET, URL("/posts/missing"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.NOT_FOUND

def test_runs_component_after_hooks_for_http_errors():
	class Post(Model):
		pass

	class RecordingComponent(Component):
		def __init__(self):
			self.statuses = []

		def after(self, res, ctx):
			self.statuses.append(res.status)
			res.headers["X-After"] = "ran"

	component = RecordingComponent()
	unmatched_app = Application([], [component])
	unmatched_res = unmatched_app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	missing_model_app = Application([
		Route(Method.GET, Pattern("/posts/missing"), show)
	], [component])
	missing_model_res = missing_model_app.handle(
		Request(Method.GET, URL("/posts/missing"), Headers(), Input())
	)

	assert component.statuses == [Status.NOT_FOUND, Status.NOT_FOUND]
	assert str(unmatched_res.headers["X-After"]) == "ran"
	assert str(missing_model_res.headers["X-After"]) == "ran"
