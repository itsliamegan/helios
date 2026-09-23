from collections.abc import Callable
import sys
import traceback

from helios.http import Method, Request, Response, Status, Stream
from helios.http.error import HTTPError
from helios.routing import Router

from .container import Container
from .context import Context

type Next = Callable[[Request, Context], Response]
type Middleware = Callable[[Request, Context, Next], Response]


class Kernel:
	def __init__(
		self,
		container: Container,
		router: Router,
		middlewares: list[Middleware],
	):
		self.container = container
		self.pipeline = self.build(router, middlewares)

	def handle(self, request: Request) -> Response:
		context = Context(self.container, request)
		try:
			return self.pipeline(request, context)
		finally:
			context.close()

	def build(self, router: Router, middlewares: list[Middleware]) -> Next:
		next: Next = self.render_http_errors(router)
		for middleware in reversed(middlewares):
			next = self.render_http_errors(self.bind(middleware, next))
		next = self.bind(self.adapt_artificial_method, next)
		next = self.bind(self.capture_errors, next)
		return self.bind(self.ensure_content_length, next)

	@staticmethod
	def bind(middleware: Middleware, next: Next) -> Next:
		def call(request: Request, context: Context) -> Response:
			return middleware(request, context, next)

		return call

	@staticmethod
	def render_http_errors(next: Next) -> Next:
		def call(request: Request, context: Context) -> Response:
			try:
				return next(request, context)
			except HTTPError as error:
				context.error = error
				return Response.text(f"{error.status}", error.status)

		return call

	@staticmethod
	def ensure_content_length(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		response = next(request, context)
		if isinstance(response.body, Stream):
			return response
		else:
			if "Content-Length" not in response.headers:
				response.headers["Content-Length"] = str(len(response.body.to_bytes()))
			return response

	@staticmethod
	def adapt_artificial_method(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		if "_method" in request.input:
			raw_method = request.input["_method"]
			del request.input["_method"]
			if raw_method == "GET":
				request.method = Method.GET
			elif raw_method == "POST":
				request.method = Method.POST
			elif raw_method == "PUT":
				request.method = Method.PUT
			elif raw_method == "PATCH":
				request.method = Method.PATCH
			elif raw_method == "DELETE":
				request.method = Method.DELETE
		return next(request, context)

	@staticmethod
	def capture_errors(request: Request, context: Context, next: Next) -> Response:
		try:
			return next(request, context)
		except Exception as error:
			context.error = error
			traceback.print_exception(error, file=sys.stderr)
			return Response.text(
				"500 Internal Server Error",
				Status.INTERNAL_SERVER_ERROR,
			)
