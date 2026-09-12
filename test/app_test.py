from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises

import helios.app
from helios.app import (
	Application,
	Component,
	ComponentError,
	Context,
	Lifetime,
	Thread,
)
from helios.data.model import Model
from helios.data.store import Store
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.routing import NotFoundError, Pattern, Route, Router, URLs


def test_boots_components():
	class ExampleComponent(Component[object]):
		provides = object

		def boot(self):
			self.booted = True

		def provide(self, ctx):
			return self

	component = ExampleComponent()
	app = Application(helios.app.Config(), Router([]), [component])

	app.boot()

	assert_eq(component.booted, True)


def test_manages_component_resources():
	events = []

	class Resource:
		def __enter__(self):
			events.append("enter")
			return self

		def __exit__(self, *_):
			events.append("exit")

	class ResourceComponent(Component[Resource]):
		provides = Resource

		def provide(self, ctx):
			resource = ctx.enter(Resource())
			events.append("provide")
			return resource

		def finish(self, res, ctx):
			events.append("finish")

	def index(req, ctx):
		events.append("handler")
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[ResourceComponent()],
	)

	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(events, ["enter", "provide", "handler", "finish", "exit"])


def test_binds_provided_value_to_context():
	class ExampleComponent(Component[str]):
		provides = str

		def provide(self, ctx):
			return "provided"

	def index(req, ctx):
		return Response.text(ctx.get(str))

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[ExampleComponent()],
	)
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(str(res.body), "provided")


def test_provides_configured_route_urls_to_context():
	def index(req, ctx):
		urls = ctx.get(URLs)
		return Response.text(str(urls.route("home")))

	router = Router([Route(Method.GET, Pattern("/"), index, name="home")])
	app = Application(helios.app.Config(URL("https://example.com:8443")), router, [])

	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(str(res.body), "https://example.com:8443/")


def test_provides_application_component_once():
	provided = object()
	provide_calls = []
	seen = []

	class ExampleComponent(Component[object]):
		lifetime = Lifetime.APPLICATION
		provides = object
		requires = (Router,)

		def provide(self, ctx):
			ctx.get(Router)
			provide_calls.append(ctx)
			return provided

		def finish(self, res, ctx):
			raise RuntimeError

	def index(req, ctx):
		seen.append(ctx.get(object))
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[ExampleComponent()],
	)
	app.boot()

	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))
	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(len(provide_calls), 1)
	assert_eq(seen, [provided, provided])


def test_provides_request_to_context():
	def index(req, ctx):
		return Response.text(str(ctx.get(Request) is req))

	app = Application(
		helios.app.Config(), Router([Route(Method.GET, Pattern("/"), index)]), []
	)
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert_eq(str(res.body), "True")


def test_rejects_component_without_provided_value():
	class InvalidComponent(Component):
		pass

	with assert_raises(ComponentError):
		Application(helios.app.Config(), Router([]), [InvalidComponent()])


def test_rejects_unsatisfied_component_requirement():
	class DependentComponent(Component[int]):
		provides = int
		requires = (str,)

		def provide(self, ctx):
			return self

	with assert_raises(ComponentError):
		Application(helios.app.Config(), Router([]), [DependentComponent()])


def test_rejects_unsatisfied_middleware_requirement():
	class Middleware:
		requires = (str,)

		def __call__(self, req, ctx, next):
			return next(req, ctx)

	with assert_raises(ComponentError):
		Application(helios.app.Config(), Router([]), [], middlewares=[Middleware()])


def test_rejects_duplicate_provided_values():
	class FirstComponent(Component[str]):
		provides = str

		def provide(self, ctx):
			return self

	class SecondComponent(Component[str]):
		provides = str

		def provide(self, ctx):
			return self

	with assert_raises(ComponentError):
		Application(
			helios.app.Config(), Router([]), [FirstComponent(), SecondComponent()]
		)


def test_get_rejects_unprovided_type():
	with assert_raises(ComponentError):
		Context().get(str)


def test_gets_value_from_parent_context():
	parent = Context()
	parent.put(str, "provided")

	assert_eq(Context(parent).get(str), "provided")


def test_rejects_application_requirement_from_request_component():
	class RequestComponent(Component[str]):
		provides = str

	class ApplicationComponent(Component[int]):
		lifetime = Lifetime.APPLICATION
		provides = int
		requires = (str,)

	with assert_raises(ComponentError):
		Application(
			helios.app.Config(),
			Router([]),
			[RequestComponent(), ApplicationComponent()],
		)


def test_runs_providerless_component():
	events = []

	class RecordingComponent(Component[None]):
		provides = None

		def finish(self, res, ctx):
			events.append("finish")

	app = Application(helios.app.Config(), Router([]), [RecordingComponent()])

	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(events, ["finish"])


def test_ensures_content_length():
	def index(req, ctx):
		return Response.text("Hello, world!")

	app = Application(
		helios.app.Config(), Router([Route(Method.GET, Pattern("/"), index)]), []
	)
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert_eq(str(res.headers["Content-Length"]), "13")


def test_adapts_artificial_method():
	def destroy(req, ctx):
		return Response.empty()

	app = Application(
		helios.app.Config(), Router([Route(Method.DELETE, Pattern("/"), destroy)]), []
	)
	req = Request(Method.GET, URL("/"), Headers(), Input({"_method": "DELETE"}))

	res = app.handle(req)

	assert_eq(res.status, Status.NO_CONTENT)


def test_captures_errors():
	def index(req, ctx):
		raise RuntimeError

	app = Application(
		helios.app.Config(), Router([Route(Method.GET, Pattern("/"), index)]), []
	)
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)


def test_handles_route_not_found():
	app = Application(helios.app.Config(), Router([]), [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert_eq(res.status, Status.NOT_FOUND)


def test_handles_model_not_found():
	class Post(Model):
		pass

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/posts/missing"), show)]),
		[],
	)
	req = Request(Method.GET, URL("/posts/missing"), Headers(), Input())

	res = app.handle(req)

	assert_eq(res.status, Status.NOT_FOUND)


def test_runs_component_finish_hooks_for_http_errors():
	class Post(Model):
		pass

	class RecordingComponent(Component[object]):
		provides = object

		def __init__(self):
			self.statuses = []

		def provide(self, ctx):
			return self

		def finish(self, res, ctx):
			self.statuses.append(res.status)
			res.headers["X-Finish"] = "ran"

	component = RecordingComponent()
	unmatched_app = Application(helios.app.Config(), Router([]), [component])
	unmatched_res = unmatched_app.handle(
		Request(Method.GET, URL("/"), Headers(), Input())
	)

	def show(req, ctx):
		Store().find_one(Post, uuid4())

	missing_model_app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/posts/missing"), show)]),
		[component],
	)
	missing_model_res = missing_model_app.handle(
		Request(Method.GET, URL("/posts/missing"), Headers(), Input())
	)

	assert_eq(component.statuses, [Status.NOT_FOUND, Status.NOT_FOUND])
	assert_eq(str(unmatched_res.headers["X-Finish"]), "ran")
	assert_eq(str(missing_model_res.headers["X-Finish"]), "ran")


def test_runs_configured_middleware_inside_components():
	events = []

	class ExampleComponent(Component[str]):
		provides = str

		def provide(self, ctx):
			events.append("provide")
			return "provided"

		def finish(self, res, ctx):
			events.append("finish")

	class Middleware:
		requires = (str,)

		def __call__(self, req, ctx, next):
			events.append(ctx.get(str))
			return next(req, ctx)

	def index(req, ctx):
		events.append("handler")
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[ExampleComponent()],
		middlewares=[Middleware()],
	)

	app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(events, ["provide", "provided", "handler", "finish"])


def test_builds_a_middleware_thread_around_a_last_callable():
	def middleware(req, ctx, next):
		res = next(req, ctx)
		res.headers["X-Middleware"] = "ran"
		return res

	def last(req, ctx):
		return Response.text("Dispatched")

	thread = Thread.build([middleware], last)
	res = thread(Request(Method.GET, URL("/anything"), Headers(), Input()), None)

	assert_eq(str(res.body), "Dispatched")
	assert_eq(str(res.headers["X-Middleware"]), "ran")


def test_runs_component_finish_hooks_for_guard_responses():
	class RecordingComponent(Component[object]):
		provides = object

		def provide(self, ctx):
			return self

		def finish(self, res, ctx):
			res.headers["X-Finish"] = "ran"

	def guard(req, ctx):
		return Response.text("Forbidden", Status.FORBIDDEN)

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), handler, guards=[guard])]),
		[RecordingComponent()],
	)
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(res.status, Status.FORBIDDEN)
	assert_eq(str(res.headers["X-Finish"]), "ran")


def test_handles_guard_http_errors_inside_component_chain():
	class RecordingComponent(Component[object]):
		provides = object

		def provide(self, ctx):
			return self

		def finish(self, res, ctx):
			res.headers["X-Finish"] = "ran"

	def guard(req, ctx):
		raise NotFoundError()

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), handler, guards=[guard])]),
		[RecordingComponent()],
	)
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(res.status, Status.NOT_FOUND)
	assert_eq(str(res.headers["X-Finish"]), "ran")


def test_captures_unexpected_guard_errors():
	def guard(req, ctx):
		raise RuntimeError

	def handler(req, ctx):
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), handler, guards=[guard])]),
		[],
	)
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))

	assert_eq(res.status, Status.INTERNAL_SERVER_ERROR)
