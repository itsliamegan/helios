from contextlib import contextmanager

from luna.test.assertion import assert_eq

from helios.app import Container, Kernel
from helios.http import (
	Buffered,
	Cookies,
	Headers,
	Method,
	Request,
	Response,
	Status,
	URL,
)
from helios.routing import NotFoundError, Pattern, Route, Router


def request() -> Request:
	return Request(Method.GET, URL("/"))


def test_records_handled_errors_for_outer_middleware():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.error)
		return response

	kernel = Kernel(Container(), Router([]), [observe])
	response = kernel.handle(request())

	assert_eq(response.status, Status.NOT_FOUND)
	assert isinstance(seen[0], NotFoundError)
	assert_eq(str(response.headers["Content-Length"]), "13")


def test_content_length_uses_encoded_body_size():
	def index(request, context):
		return Response(Status.OK, Headers(), Cookies(), Buffered(b"\x00\xff"))

	kernel = Kernel(
		Container(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[],
	)

	response = kernel.handle(request())

	assert_eq(str(response.headers["Content-Length"]), "2")


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
		Router([Route(Method.GET, Pattern("/"), index)]),
		[observe],
	)
	response = kernel.handle(request())

	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
	assert_eq(str(response.headers["Content-Length"]), "25")
	assert_eq(events, ["closed"])


def test_returned_error_response_has_no_context_error():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.error)
		return response

	def index(request, context):
		return Response.text("failed", Status.INTERNAL_SERVER_ERROR)

	kernel = Kernel(
		Container(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[observe],
	)
	kernel.handle(request())

	assert_eq(seen, [None])
