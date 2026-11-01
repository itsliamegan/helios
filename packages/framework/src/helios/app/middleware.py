from collections.abc import Callable, Sequence

from helios.http import Request, Response
from helios.http.error import HTTPError

from .context import Context


class Middlewares:
	"""Middleware in the order a request passes through it.

	Building the middleware chains it to a destination. An `HTTPError` renders
	as a response at the layer that raised it, so the middleware around that
	layer still receives a response. The request's context records the first
	such error as its failure.
	"""

	def __init__(self, middlewares: Sequence[Middleware] | None = None):
		self.middlewares = list(middlewares or [])

	def build(self, destination: Next) -> Next:
		def with_rendered_http_errors(middleware: Middleware, next: Next) -> Next:
			def call(request: Request, context: Context) -> Response:
				try:
					return middleware(request, context, next)
				except HTTPError as error:
					if context.failure is None:
						context.failure = error
					return Response.error(error)

			return call

		next = with_rendered_http_errors(
			lambda request, context, next: next(request, context),
			destination,
		)
		for middleware in reversed(self.middlewares):
			next = with_rendered_http_errors(middleware, next)
		return next

	def prepend(self, *middlewares: Middleware):
		self.middlewares[0:0] = middlewares

	def append(self, *middlewares: Middleware):
		self.middlewares.extend(middlewares)


type Middleware = Callable[[Request, Context, Next], Response]
type Next = Callable[[Request, Context], Response]
