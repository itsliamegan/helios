from collections.abc import Callable, Sequence
import sys
import traceback

from helios.http import Method, Request, Response
from helios.http.error import (
	BadRequestError,
	ForbiddenError,
	HTTPError,
	InternalServerError,
	UnsupportedMethodError,
)
from helios.routing import Router
from helios.url import URL

from .container import Container
from .context import Context


class Kernel:
	"""Runs each request through a chain of middleware to the router.

	An `HTTPError` renders as a response at the layer that raised it, so the
	middleware around that layer still receives a response. Any other error
	becomes a server error at the outermost layer, past every middleware. In
	both cases, the request's context records the first error as its failure.
	"""

	def __init__(
		self,
		container: Container,
		router: Router,
		middlewares: Sequence[Middleware],
	):
		self.container = container
		self.pipeline = self.build(router, middlewares)

	def handle(self, request: Request) -> Response:
		try:
			with Context(self.container, request) as context:
				return self.pipeline(request, context)
		except Exception as error:
			# To reach this, the cleanup of a request-scoped service must have
			# raised. The kernel captures all other errors inside the pipeline.
			traceback.print_exception(error, file=sys.stderr)
			return Response.error(InternalServerError())

	def build(self, router: Router, middlewares: Sequence[Middleware]) -> Next:
		next: Next = self.render_http_errors(router)
		for middleware in reversed(middlewares):
			next = self.render_http_errors(self.bind(middleware, next))
		next = self.render_http_errors(self.bind(self.prevent_request_forgery, next))
		next = self.render_http_errors(self.bind(self.adapt_artificial_method, next))
		return self.bind(self.capture_errors, next)

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
				if context.failure is None:
					context.failure = error
				return Response.error(error)

		return call

	@staticmethod
	def adapt_artificial_method(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		"""Take the method from a `_method` form field, if one was sent.

		HTML forms can only send `GET` and `POST`, so this lets a form send the
		other methods. The field is removed from the input.
		"""

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
	def prevent_request_forgery(
		request: Request,
		context: Context,
		next: Next,
	) -> Response:
		"""Reject a state-changing request that a browser sent from another origin.

		A `GET` request always passes. A request with `Sec-Fetch-Site` passes only
		from the same origin. Otherwise, a request with `Origin` passes only when
		that origin has the request's host and port. A request with neither header
		did not come from a current browser, so it passes.
		"""

		if request.method is Method.GET:
			return next(request, context)

		if "Sec-Fetch-Site" in request.headers:
			if str(request.headers["Sec-Fetch-Site"]) != "same-origin":
				raise ForbiddenError("the request came from another origin")
		elif "Origin" in request.headers and not has_same_host(
			str(request.headers["Origin"]),
			request.url,
		):
			raise ForbiddenError("the request came from another host")
		return next(request, context)

	@staticmethod
	def capture_errors(request: Request, context: Context, next: Next) -> Response:
		try:
			return next(request, context)
		except Exception as error:
			if context.failure is None:
				context.failure = error
			traceback.print_exception(error, file=sys.stderr)
			return Response.error(InternalServerError())


def has_same_host(raw_origin: str, url: URL) -> bool:
	try:
		origin = URL.parse(raw_origin)
	except ValueError:
		return False
	if origin.host is None or url.host is None:
		return False
	return origin.host.lower() == url.host.lower() and origin.port == url.port


type Middleware = Callable[[Request, Context, Next], Response]
type Next = Callable[[Request, Context], Response]
