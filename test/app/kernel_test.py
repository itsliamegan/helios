from contextlib import contextmanager

from luna.test.assertion import assert_eq, assert_is_instance

from helios.app import Container, Kernel
from helios.http import (
	Input,
	Method,
	Request,
	Response,
	Status,
	URL,
)
from helios.http.error import ContentTooLargeError, NotFoundError
from helios.routing import Route, Router


def request() -> Request:
	return Request(Method.GET, URL("/"))


def test_records_raised_error_as_aborted_for_outer_middleware():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.aborted)
		return response

	kernel = Kernel(Container(), Router([]), [observe])
	response = kernel.handle(request())

	assert_eq(response.status, Status.NOT_FOUND)
	assert_is_instance(seen[0], NotFoundError)


def test_records_error_raised_by_inner_middleware_as_aborted():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.aborted)
		return response

	def refuse(request, context, next):
		raise ContentTooLargeError()

	kernel = Kernel(Container(), Router([]), [observe, refuse])
	response = kernel.handle(request())

	assert_eq(response.status, Status.CONTENT_TOO_LARGE)
	assert_is_instance(seen[0], ContentTooLargeError)


def test_unexpected_errors_skip_response_middleware_and_close_resources():
	events = []

	@contextmanager
	def resource():
		try:
			yield
		finally:
			events.append("closed")

	def observe(request, context, next):
		context.enter(resource())
		next(request, context)
		events.append("after")
		return Response.empty()

	def index(request, context):
		raise RuntimeError("boom")

	kernel = Kernel(
		Container(),
		Router([Route.get("/", index)]),
		[observe],
	)
	response = kernel.handle(request())

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
	assert_eq(events, ["closed"])


def test_returned_error_response_is_not_aborted():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.aborted)
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
