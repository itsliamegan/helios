from contextlib import contextmanager

from luna.test.assertion import assert_eq

from helios.app import Application, Config, Provider
from helios.http import Method, Request, Response, Status, URL
from helios.routing import Pattern, Route, Router, URLs


def request(path: str = "/") -> Request:
	return Request(Method.GET, URL(path))


def test_registers_all_providers_before_booting_in_order():
	events = []

	class RecordingProvider(Provider):
		def __init__(self, name):
			self.name = name

		def register(self, container):
			events.append(f"register {self.name}")
			if self.name == "second":
				container.instance(str, "registered")

		def boot(self, application):
			events.append(f"boot {self.name} {application.container.get(str)}")

	Application(
		Config(), Router([]), [RecordingProvider("first"), RecordingProvider("second")]
	)

	assert_eq(
		events,
		[
			"register first",
			"register second",
			"boot first registered",
			"boot second registered",
		],
	)


def test_closes_request_and_application_resources_in_reverse_order():
	events = []

	@contextmanager
	def resource(name):
		events.append(f"enter {name}")
		try:
			yield name
		finally:
			events.append(f"exit {name}")

	class Resources(Provider):
		def register(self, container):
			container.scoped(str, self.value)

		def boot(self, application):
			application.container.enter(resource("application one"))
			application.container.enter(resource("application two"))

		def value(self, context):
			context.enter(resource("request one"))
			context.enter(resource("request two"))
			return "value"

	def index(request, context):
		context.get(str)
		return Response.empty(Status.OK)

	app = Application(
		Config(), Router([Route(Method.GET, Pattern("/"), index)]), [Resources()]
	)
	app.handle(request())
	app.close()
	app.close()

	assert_eq(
		events,
		[
			"enter application one",
			"enter application two",
			"enter request one",
			"enter request two",
			"exit request two",
			"exit request one",
			"exit application two",
			"exit application one",
		],
	)


def test_runs_provider_then_standalone_middleware_in_order():
	events = []

	class Middlewares(Provider):
		def __init__(self, name):
			self.name = name

		def boot(self, application):
			application.use(self.middleware)

		def middleware(self, request, context, next):
			events.append(f"before {self.name}")
			response = next(request, context)
			events.append(f"after {self.name}")
			return response

	def standalone(request, context, next):
		events.append("before standalone")
		response = next(request, context)
		events.append("after standalone")
		return response

	def index(request, context):
		events.append("handler")
		return Response.empty(Status.OK)

	app = Application(
		Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[Middlewares("one"), Middlewares("two")],
		[standalone],
	)
	app.handle(request())

	assert_eq(
		events,
		[
			"before one",
			"before two",
			"before standalone",
			"handler",
			"after standalone",
			"after two",
			"after one",
		],
	)


def test_provides_framework_bindings():
	def index(request, context):
		urls = context.get(URLs)
		return Response.text(str(urls.route("home", absolute=True)))

	router = Router([Route(Method.GET, Pattern("/"), index, name="home")])
	app = Application(Config(URL("https://example.com:8443")), router, [])

	assert_eq(str(app.handle(request()).body), "https://example.com:8443/")
