from typing import cast

from luna.test.assertion import assert_eq, assert_is, assert_is_instance

from helios.app import Container, Kernel, Middlewares, Rescues
from helios.http import Headers, Input, Method, Request, Response, Status
from helios.http.body import Stream
from helios.http.error import NotFoundError
from helios.routing import Route, Router
from helios.url import URL


class Visit:
	pass


class Reader:
	pass


def request() -> Request:
	return Request(Method.GET, URL("/"))


def test_releases_request_services_with_raised_http_error():
	seen = []

	def visit(context):
		try:
			yield Visit()
		except Exception as error:
			seen.append(error)
			raise

	def resolve(request, context, next):
		context.get(Visit)
		return next(request, context)

	container = Container()
	container.scoped(Visit, visit)
	kernel = Kernel(container, Router([]), Middlewares([resolve]), Rescues())
	kernel.handle(request())

	assert_is_instance(seen[0], NotFoundError)


def test_releases_request_services_with_unexpected_error():
	seen = []

	def visit(context):
		try:
			yield Visit()
		except Exception as error:
			seen.append(error)
			raise

	def index(request, context):
		context.get(Visit)
		raise ValueError("failed")

	container = Container()
	container.scoped(Visit, visit)
	kernel = Kernel(
		container, Router([Route.get("/", index)]), Middlewares(), Rescues()
	)
	kernel.handle(request())

	assert_is_instance(seen[0], ValueError)


def test_releases_request_services_before_stream_is_read():
	events = []

	def visit(context):
		yield Visit()
		events.append("released")

	def chunks():
		events.append("read")
		yield b"one"
		yield b"two"

	def index(request, context):
		context.get(Visit)
		return Response.stream(chunks(), "text/plain")

	container = Container()
	container.scoped(Visit, visit)
	kernel = Kernel(
		container, Router([Route.get("/", index)]), Middlewares(), Rescues()
	)
	response = kernel.handle(request())
	body = cast(Stream, response.body)

	assert_eq(events, ["released"])
	assert_eq(list(body.chunks), [b"one", b"two"])
	assert_eq(events, ["released", "read"])


def test_release_error_becomes_server_error_response():
	def visit(context):
		yield Visit()
		raise ValueError("failed")

	def index(request, context):
		context.get(Visit)
		return Response.empty(Status.OK)

	container = Container()
	container.scoped(Visit, visit)
	kernel = Kernel(
		container, Router([Route.get("/", index)]), Middlewares(), Rescues()
	)
	response = kernel.handle(request())

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)


def test_cleanups_after_failed_release_see_its_error():
	seen = []
	failure = ValueError("failed")

	def reader(context):
		try:
			yield Reader()
		except Exception as error:
			seen.append(error)
			raise

	def visit(context):
		yield Visit()
		raise failure

	def index(request, context):
		context.get(Reader)
		context.get(Visit)
		return Response.empty(Status.OK)

	container = Container()
	container.scoped(Reader, reader)
	container.scoped(Visit, visit)
	kernel = Kernel(
		container, Router([Route.get("/", index)]), Middlewares(), Rescues()
	)
	kernel.handle(request())

	assert_is(seen[0], failure)


def test_unexpected_errors_skip_response_middleware_and_close_resources():
	events = []

	def visit(context):
		try:
			yield Visit()
		finally:
			events.append("closed")

	def observe(request, context, next):
		context.get(Visit)
		next(request, context)
		events.append("after")
		return Response.empty()

	def index(request, context):
		raise RuntimeError("boom")

	container = Container()
	container.scoped(Visit, visit)
	kernel = Kernel(
		container,
		Router([Route.get("/", index)]),
		Middlewares([observe]),
		Rescues(),
	)
	response = kernel.handle(request())

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
	assert_eq(events, ["closed"])


def test_returned_error_response_is_not_a_failure():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.failure)
		return response

	def index(request, context):
		return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

	kernel = Kernel(
		Container(),
		Router([Route.get("/", index)]),
		Middlewares([observe]),
		Rescues(),
	)
	kernel.handle(request())

	assert_eq(seen, [None])


def test_overrides_method_from_input():
	def destroy(request, context):
		return Response.text(f"{"_method" in request.input}")

	kernel = Kernel(
		Container(),
		Router([Route.delete("/", destroy)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(Method.POST, URL("/"), input=Input({"_method": "DELETE"}))
	)

	assert_eq(response.status, Status.OK)
	assert_eq(str(response.body), "False")


def test_rejects_unknown_method_override_as_bad_request():
	def destroy(request, context):
		return Response.empty()

	kernel = Kernel(
		Container(),
		Router([Route.delete("/", destroy)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(Method.POST, URL("/"), input=Input({"_method": "delete"}))
	)

	assert_eq(response.status, Status.BAD_REQUEST)


def test_passes_get_from_another_site():
	def index(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.get("/posts", index)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.GET,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "cross-site"}),
		)
	)

	assert_eq(response.status, Status.OK)


def test_passes_same_origin_request():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "same-origin"}),
		)
	)

	assert_eq(response.status, Status.OK)


def test_rejects_same_site_request():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "same-site"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_cross_site_request():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "cross-site"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_user_initiated_request():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "none"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_unknown_fetch_site():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "same-planet"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_passes_request_without_browser_headers():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
		)
	)

	assert_eq(response.status, Status.OK)


def test_passes_origin_with_same_host():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "https://blog.example"}),
		)
	)

	assert_eq(response.status, Status.OK)


def test_ignores_origin_scheme():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "http://blog.example"}),
		)
	)

	assert_eq(response.status, Status.OK)


def test_ignores_origin_host_case():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "https://Blog.Example"}),
		)
	)

	assert_eq(response.status, Status.OK)


def test_rejects_origin_with_other_host():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "https://spam.example"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_origin_with_other_port():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "https://blog.example:8443"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_null_origin():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "null"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_malformed_origin():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Origin": "https://[blog.example"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_prefers_fetch_site_over_origin():
	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers(
				{
					"Sec-Fetch-Site": "cross-site",
					"Origin": "https://blog.example",
				}
			),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_checks_overridden_method():
	def destroy(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.delete("/posts", destroy)]),
		Middlewares(),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.GET,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "cross-site"}),
			input=Input({"_method": "DELETE"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)


def test_rejects_before_middleware():
	seen = []

	def observe(request, context, next):
		seen.append(request)
		return next(request, context)

	def store(request, context):
		return Response.empty(Status.OK)

	kernel = Kernel(
		Container(),
		Router([Route.post("/posts", store)]),
		Middlewares([observe]),
		Rescues(),
	)
	response = kernel.handle(
		Request(
			Method.POST,
			URL.parse("https://blog.example/posts"),
			headers=Headers({"Sec-Fetch-Site": "cross-site"}),
		)
	)

	assert_eq(response.status, Status.FORBIDDEN)
	assert_eq(seen, [])
