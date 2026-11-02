import sys
import traceback

from helios.http import Method, Request, Response
from helios.http.error import (
	BadRequestError,
	ForbiddenError,
	UnsupportedMethodError,
)
from helios.routing import Router
from helios.url import URL

from .container import Container
from .context import Context
from .middleware import Handler, Middlewares
from .rescues import Rescues


class Kernel:
	"""Runs each request through middleware to the router.

	The kernel requires its own middleware, so it runs first. An error that
	is not rescued becomes a server error at the outermost layer, past every
	middleware. The request's context records that error as its failure
	unless it already has one.
	"""

	def __init__(
		self,
		container: Container,
		router: Router,
		middlewares: Middlewares,
		rescues: Rescues,
	):
		middlewares.require(
			self.capture_errors,
			self.adapt_artificial_method,
			self.prevent_request_forgery,
		)

		self.container = container
		self.rescues = rescues
		self.pipeline = middlewares.build(router, rescues)

	def handle(self, request: Request) -> Response:
		try:
			with Context(self.container, request) as context:
				return self.pipeline(request, context)
		except Exception as error:
			# To reach this, the cleanup of a request-scoped service must have
			# raised. The kernel captures all other errors inside the pipeline.
			traceback.print_exception(error, file=sys.stderr)
			return self.rescues.render(error)

	def capture_errors(
		self, request: Request, context: Context, next: Handler
	) -> Response:
		try:
			return next(request, context)
		except Exception as error:
			if context.failure is None:
				context.failure = error
			traceback.print_exception(error, file=sys.stderr)
			return self.rescues.render(error)

	@staticmethod
	def adapt_artificial_method(
		request: Request,
		context: Context,
		next: Handler,
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
		next: Handler,
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
		elif "Origin" in request.headers:
			try:
				origin = URL.parse(str(request.headers["Origin"]))
			except ValueError as error:
				raise ForbiddenError("the request has a malformed origin") from error
			if (
				origin.host is None
				or request.url.host is None
				or origin.host.lower() != request.url.host.lower()
			):
				raise ForbiddenError("the request came from another host")
			if origin.port != request.url.port:
				raise ForbiddenError("the request came from another port")
		return next(request, context)
