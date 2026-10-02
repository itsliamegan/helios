from collections.abc import Callable
import sys
import traceback

from helios.http import Buffered, Method, Request, Response, Status
from helios.http.error import BadRequestError, HTTPError, UnsupportedMethodError
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

	@staticmethod
	def reject(error: HTTPError) -> Response:
		response = Kernel.render(error)
		Kernel.set_content_length(response)
		return response

	def build(self, router: Router, middlewares: list[Middleware]) -> Next:
		next: Next = self.render_http_errors(router)
		for middleware in reversed(middlewares):
			next = self.render_http_errors(self.bind(middleware, next))
		next = self.render_http_errors(self.bind(self.adapt_artificial_method, next))
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
				context.aborted = error
				return Kernel.render(error)

		return call

	@staticmethod
	def render(error: HTTPError) -> Response:
		return Response.text(f"{error.status}", error.status)

	@staticmethod
	def ensure_content_length(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		response = next(request, context)
		Kernel.set_content_length(response)
		return response

	@staticmethod
	def set_content_length(response: Response):
		if (
			isinstance(response.body, Buffered)
			and "Content-Length" not in response.headers
		):
			response.headers["Content-Length"] = str(len(response.body.to_bytes()))

	@staticmethod
	def adapt_artificial_method(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		raw_method = request.input.first("_method")
		if raw_method is not None:
			del request.input["_method"]
			try:
				request.method = Method.parse(raw_method)
			except UnsupportedMethodError as error:
				raise BadRequestError(
					f"invalid method override {raw_method!r}"
				) from error
		return next(request, context)

	@staticmethod
	def capture_errors(request: Request, context: Context, next: Next) -> Response:
		try:
			return next(request, context)
		except Exception as error:
			traceback.print_exception(error, file=sys.stderr)
			return Response.text(
				"500 Internal Server Error",
				Status.INTERNAL_SERVER_ERROR,
			)
