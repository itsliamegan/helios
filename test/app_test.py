from helios.app import Application, Component, Thread
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import NotFoundError, Pattern, Route, Router
from helios.store import Model, Store

from uuid import uuid4

def test_boots_components():
	class ExampleComponent(Component):
		def boot(self):
			self.booted = True

	component = ExampleComponent()
	app = Application(Router([]), [component])

	app.boot()

	assert component.booted == True

def test_ensures_content_length():
	def index(req, ctx):
		return Response.text("Hello, world!")

	app = Application(Router([Route(Method.GET, Pattern("/"), index)]), [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert str(res.headers["Content-Length"]) == "13"

def test_adapts_artificial_method():
	def destroy(req, ctx):
		return Response.empty()

	app = Application(Router([Route(Method.DELETE, Pattern("/"), destroy)]), [])
	req = Request(Method.GET, URL("/"), Headers(), Input({"_method": "DELETE"}))

	res = app.handle(req)

	assert res.status == Status.NO_CONTENT

def test_captures_errors():
	def index(req, ctx):
		raise RuntimeError

	app = Application(Router([Route(Method.GET, Pattern("/"), index)]), [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.INTERNAL_SERVER_ERROR

def test_handles_route_not_found():
	app = Application(Router([]), [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.NOT_FOUND

def test_handles_model_not_found():
	class Post(Model):
		pass

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	app = Application(Router([Route(Method.GET, Pattern("/posts/missing"), show)]), [])
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
	unmatched_app = Application(Router([]), [component])
	unmatched_res = unmatched_app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	missing_model_app = Application(Router([
		Route(Method.GET, Pattern("/posts/missing"), show)
	]), [component])
	missing_model_res = missing_model_app.handle(
		Request(Method.GET, URL("/posts/missing"), Headers(), Input())
	)

	assert component.statuses == [Status.NOT_FOUND, Status.NOT_FOUND]
	assert str(unmatched_res.headers["X-After"]) == "ran"
	assert str(missing_model_res.headers["X-After"]) == "ran"

def test_builds_a_middleware_thread_around_a_last_callable():
	def middleware(req, ctx, next):
		res = next(req, ctx)
		res.headers["X-Middleware"] = "ran"
		return res

	def last(req, ctx):
		return Response.text("Dispatched")

	thread = Thread.build([middleware], last)
	res = thread(Request(Method.GET, URL("/anything"), Headers(), Input()), None)

	assert str(res.body) == "Dispatched"
	assert str(res.headers["X-Middleware"]) == "ran"

def test_runs_component_after_hooks_for_guard_responses():
	class RecordingComponent(Component):
		def after(self, res, ctx):
			res.headers["X-After"] = "ran"

	def guard(req, ctx):
		return Response.text("Forbidden", Status.FORBIDDEN)

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(Router([
		Route(Method.GET, Pattern("/"), handler, guards=[guard])
	]), [RecordingComponent()])
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert res.status == Status.FORBIDDEN
	assert str(res.headers["X-After"]) == "ran"

def test_handles_guard_http_errors_inside_component_chain():
	class RecordingComponent(Component):
		def after(self, res, ctx):
			res.headers["X-After"] = "ran"

	def guard(req, ctx):
		raise NotFoundError()

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(Router([
		Route(Method.GET, Pattern("/"), handler, guards=[guard])
	]), [RecordingComponent()])
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert res.status == Status.NOT_FOUND
	assert str(res.headers["X-After"]) == "ran"

def test_captures_unexpected_guard_errors():
	def guard(req, ctx):
		raise RuntimeError

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(Router([
		Route(Method.GET, Pattern("/"), handler, guards=[guard])
	]), [])
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert res.status == Status.INTERNAL_SERVER_ERROR
