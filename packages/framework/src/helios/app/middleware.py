from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass

from helios.http import Request, Response
from helios.http.error import HTTPError

from .context import Context


@dataclass(init=False)
class Middlewares:
	"""An application's middleware in the order a request passes through it.

	Required middleware runs first. Middleware that providers use runs next.
	The middleware the application was constructed with runs last. Each tier
	keeps the order its middleware was added in.

	A chain of middleware terminates in a destination. An `HTTPError` renders
	as a response at the layer that raised it, so the middleware around that
	layer still receives a response. The request's context records the first
	such error as its failure.
	"""

	required: list[Middleware]
	provided: list[Middleware]
	application: list[Middleware]

	def __init__(self, middlewares: Sequence[Middleware] | None = None):
		self.required = []
		self.provided = []
		self.application = list(middlewares or [])

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
		for middleware in reversed(list(self)):
			next = with_rendered_http_errors(middleware, next)
		return next

	def require(self, *middlewares: Middleware):
		self.required.extend(middlewares)

	def provide(self, middleware: Middleware):
		self.provided.append(middleware)

	def __iter__(self) -> Iterator[Middleware]:
		yield from self.required
		yield from self.provided
		yield from self.application


type Middleware = Callable[[Request, Context, Next], Response]
type Next = Callable[[Request, Context], Response]
