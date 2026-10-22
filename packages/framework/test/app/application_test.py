from luna.test.assertion import assert_eq, assert_raises

from helios.app import Application, Config, Provider
from helios.http import Method, Request, Response, Status, URL
from helios.routing import Route, Router, URLs


class Moderator:
	pass


class Newsletter:
	pass


class Reader:
	pass


class Visit:
	pass


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

	app = Application(
		Config(), Router([]), [RecordingProvider("first"), RecordingProvider("second")]
	)
	app.boot()

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

	class Resources(Provider):
		def register(self, container):
			container.singleton(Moderator, self.moderator)
			container.singleton(Newsletter, self.newsletter)
			container.scoped(Reader, self.reader)
			container.scoped(Visit, self.visit)

		def boot(self, application):
			application.container.get(Moderator)
			application.container.get(Newsletter)

		def moderator(self, container):
			events.append("enter application one")
			yield Moderator()
			events.append("exit application one")

		def newsletter(self, container):
			events.append("enter application two")
			yield Newsletter()
			events.append("exit application two")

		def reader(self, context):
			events.append("enter request one")
			yield Reader()
			events.append("exit request one")

		def visit(self, context):
			events.append("enter request two")
			yield Visit()
			events.append("exit request two")

	def index(request, context):
		context.get(Reader)
		context.get(Visit)
		return Response.empty(Status.OK)

	app = Application(Config(), Router([Route.get("/", index)]), [Resources()])
	app.boot()
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
		Router([Route.get("/", index)]),
		[Middlewares("one"), Middlewares("two")],
		[standalone],
	)
	app.boot()
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

	router = Router([Route.get("/", index, name="home")])
	app = Application(Config(URL.parse("https://example.com:8443")), router, [])
	app.boot()

	assert_eq(str(app.handle(request()).body), "https://example.com:8443/")


def test_registers_providers_without_booting_them():
	events = []

	class RecordingProvider(Provider):
		def register(self, container):
			events.append("register")

		def boot(self, application):
			events.append("boot")

	Application(Config(), Router([]), [RecordingProvider()])

	assert_eq(events, ["register"])


def test_rejects_handling_before_boot():
	app = Application(Config(), Router([]), [])

	with assert_raises(RuntimeError):
		app.handle(request())


def test_closes_when_its_block_ends():
	events = []

	def moderator(container):
		yield Moderator()
		events.append("released")

	class Moderation(Provider):
		def register(self, container):
			container.singleton(Moderator, moderator)

	with Application(Config(), Router([]), [Moderation()]) as app:
		app.container.get(Moderator)
		assert_eq(events, [])

	assert_eq(events, ["released"])


def test_entering_does_not_boot():
	events = []

	class RecordingProvider(Provider):
		def boot(self, application):
			events.append("boot")

	with Application(Config(), Router([]), [RecordingProvider()]):
		pass

	assert_eq(events, [])


def test_failed_boot_releases_services_built_during_boot():
	events = []

	def moderator(container):
		try:
			yield Moderator()
		finally:
			events.append("released")

	class Moderation(Provider):
		def register(self, container):
			container.singleton(Moderator, moderator)

		def boot(self, application):
			application.container.get(Moderator)

	class Broken(Provider):
		def boot(self, application):
			raise ValueError("failed")

	app = Application(Config(), Router([]), [Moderation(), Broken()])

	with assert_raises(ValueError):
		app.boot()
	assert_eq(events, ["released"])
