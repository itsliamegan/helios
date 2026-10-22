from typing import cast

from luna.test.assertion import assert_eq, assert_is, assert_is_instance

from helios.app import Container, Kernel
from helios.http import (
	Input,
	Method,
	Request,
	Response,
	Status,
	URL,
)
from helios.http.body import Stream
from helios.http.error import BadRequestError, ContentTooLargeError, NotFoundError
from helios.routing import Route, Router


class Post:
	pass


class Author:
	pass


def request() -> Request:
	return Request(Method.GET, URL("/"))


def test_records_raised_error_as_failure_for_outer_middleware():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.failure)
		return response

	kernel = Kernel(Container(), Router([]), [observe])
	response = kernel.handle(request())

	assert_eq(response.status, Status.NOT_FOUND)
	assert_is_instance(seen[0], NotFoundError)


def test_records_error_raised_by_inner_middleware_as_failure():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.failure)
		return response

	def refuse(request, context, next):
		raise ContentTooLargeError()

	kernel = Kernel(Container(), Router([]), [observe, refuse])
	response = kernel.handle(request())

	assert_eq(response.status, Status.CONTENT_TOO_LARGE)
	assert_is_instance(seen[0], ContentTooLargeError)


def test_keeps_first_failure_when_outer_middleware_raises():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.failure)
		return response

	def reject(request, context, next):
		next(request, context)
		raise BadRequestError()

	def refuse(request, context, next):
		raise ContentTooLargeError()

	kernel = Kernel(Container(), Router([]), [observe, reject, refuse])
	response = kernel.handle(request())

	assert_eq(response.status, Status.BAD_REQUEST)
	assert_is_instance(seen[0], ContentTooLargeError)


def test_releases_request_services_with_raised_http_error():
	seen = []

	def post(context):
		try:
			yield Post()
		except Exception as error:
			seen.append(error)
			raise

	def resolve(request, context, next):
		context.get(Post)
		return next(request, context)

	container = Container()
	container.scoped(Post, post)
	kernel = Kernel(container, Router([]), [resolve])
	kernel.handle(request())

	assert_is_instance(seen[0], NotFoundError)


def test_releases_request_services_with_unexpected_error():
	seen = []

	def post(context):
		try:
			yield Post()
		except Exception as error:
			seen.append(error)
			raise

	def index(request, context):
		context.get(Post)
		raise ValueError("failed")

	container = Container()
	container.scoped(Post, post)
	kernel = Kernel(container, Router([Route.get("/", index)]), [])
	kernel.handle(request())

	assert_is_instance(seen[0], ValueError)


def test_releases_request_services_before_stream_is_read():
	events = []

	def post(context):
		yield Post()
		events.append("released")

	def chunks():
		events.append("read")
		yield b"one"
		yield b"two"

	def index(request, context):
		context.get(Post)
		return Response.stream(chunks())

	container = Container()
	container.scoped(Post, post)
	kernel = Kernel(container, Router([Route.get("/", index)]), [])
	response = kernel.handle(request())
	body = cast(Stream, response.body)

	assert_eq(events, ["released"])
	assert_eq(list(body.chunks), [b"one", b"two"])
	assert_eq(events, ["released", "read"])


def test_release_error_becomes_server_error_response():
	def post(context):
		yield Post()
		raise ValueError("failed")

	def index(request, context):
		context.get(Post)
		return Response.empty(Status.OK)

	container = Container()
	container.scoped(Post, post)
	kernel = Kernel(container, Router([Route.get("/", index)]), [])
	response = kernel.handle(request())

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)


def test_cleanups_after_failed_release_see_its_error():
	seen = []
	failure = ValueError("failed")

	def author(context):
		try:
			yield Author()
		except Exception as error:
			seen.append(error)
			raise

	def post(context):
		yield Post()
		raise failure

	def index(request, context):
		context.get(Author)
		context.get(Post)
		return Response.empty(Status.OK)

	container = Container()
	container.scoped(Author, author)
	container.scoped(Post, post)
	kernel = Kernel(container, Router([Route.get("/", index)]), [])
	kernel.handle(request())

	assert_is(seen[0], failure)


def test_unexpected_errors_skip_response_middleware_and_close_resources():
	events = []

	def post(context):
		try:
			yield Post()
		finally:
			events.append("closed")

	def observe(request, context, next):
		context.get(Post)
		next(request, context)
		events.append("after")
		return Response.empty()

	def index(request, context):
		raise RuntimeError("boom")

	container = Container()
	container.scoped(Post, post)
	kernel = Kernel(
		container,
		Router([Route.get("/", index)]),
		[observe],
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
		[observe],
	)
	kernel.handle(request())

	assert_eq(seen, [None])


def test_overrides_method_from_input():
	def destroy(request, context):
		return Response.text(f"{"_method" in request.input}")

	kernel = Kernel(
		Container(),
		Router([Route.delete("/", destroy)]),
		[],
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
		[],
	)
	response = kernel.handle(
		Request(Method.POST, URL("/"), input=Input({"_method": "delete"}))
	)

	assert_eq(response.status, Status.BAD_REQUEST)
