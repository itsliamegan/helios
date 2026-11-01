from luna.test.assertion import assert_eq, assert_is_instance, assert_raises

from helios.app import Container, Context, Middlewares
from helios.http import Method, Request, Response, Status
from helios.http.error import BadRequestError, ContentTooLargeError, NotFoundError
from helios.url import URL


def test_runs_middleware_in_order_to_destination():
	events = []

	def first(request, context, next):
		events.append("first")
		return next(request, context)

	def second(request, context, next):
		events.append("second")
		return next(request, context)

	def index(request, context):
		events.append("index")
		return Response.empty(Status.OK)

	request = Request(Method.GET, URL("/posts"))
	next = Middlewares([first, second]).build(index)
	with Context(Container(), request) as context:
		next(request, context)

	assert_eq(events, ["first", "second", "index"])


def test_prepends_middleware_before_existing_middleware():
	events = []

	def first(request, context, next):
		events.append("first")
		return next(request, context)

	def second(request, context, next):
		events.append("second")
		return next(request, context)

	def third(request, context, next):
		events.append("third")
		return next(request, context)

	def index(request, context):
		return Response.empty(Status.OK)

	middlewares = Middlewares([third])
	middlewares.prepend(first, second)
	request = Request(Method.GET, URL("/posts"))
	next = middlewares.build(index)
	with Context(Container(), request) as context:
		next(request, context)

	assert_eq(events, ["first", "second", "third"])


def test_appends_middleware_after_existing_middleware():
	events = []

	def first(request, context, next):
		events.append("first")
		return next(request, context)

	def second(request, context, next):
		events.append("second")
		return next(request, context)

	def third(request, context, next):
		events.append("third")
		return next(request, context)

	def index(request, context):
		return Response.empty(Status.OK)

	middlewares = Middlewares([first])
	middlewares.append(second, third)
	request = Request(Method.GET, URL("/posts"))
	next = middlewares.build(index)
	with Context(Container(), request) as context:
		next(request, context)

	assert_eq(events, ["first", "second", "third"])


def test_records_destination_error_as_failure_for_middleware():
	seen = []

	def observe(request, context, next):
		response = next(request, context)
		seen.append(context.failure)
		return response

	def index(request, context):
		raise NotFoundError()

	request = Request(Method.GET, URL("/posts"))
	next = Middlewares([observe]).build(index)
	with Context(Container(), request) as context:
		response = next(request, context)

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

	def index(request, context):
		return Response.empty(Status.OK)

	request = Request(Method.GET, URL("/posts"))
	next = Middlewares([observe, refuse]).build(index)
	with Context(Container(), request) as context:
		response = next(request, context)

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

	def index(request, context):
		return Response.empty(Status.OK)

	request = Request(Method.GET, URL("/posts"))
	next = Middlewares([observe, reject, refuse]).build(index)
	with Context(Container(), request) as context:
		response = next(request, context)

	assert_eq(response.status, Status.BAD_REQUEST)
	assert_is_instance(seen[0], ContentTooLargeError)


def test_raises_errors_other_than_http_errors():
	def index(request, context):
		raise ValueError("failed")

	request = Request(Method.GET, URL("/posts"))
	next = Middlewares().build(index)
	with assert_raises(ValueError), Context(Container(), request) as context:
		next(request, context)
