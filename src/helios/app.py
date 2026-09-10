from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from typing import Any, cast

from helios.http import Method, Request, Response, Status
from helios.http.error import HTTPError
from helios.routing import Router

type Next = Callable[[Request, Any], Response]
type Middleware = Callable[[Request, Any, Next], Response]


class Context:
	def __init__(self):
		self.provided: dict[type[Any], Any] = {}
		self.resources = ExitStack()

	def get[T](self, key: type[T]) -> T:
		if key not in self.provided:
			raise ComponentError(f"nothing provides {key.__qualname__}")
		return cast(T, self.provided[key])

	def put[T](self, key: type[T], val: T):
		self.provided[key] = val

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)


class ComponentError(Exception):
	pass


class Component[T]:
	provides: type[T] | None
	requires: tuple[type[Any], ...] = ()

	def boot(self):
		pass

	def provide(self, req: Request, ctx: Context) -> T:
		raise NotImplementedError

	def finish(self, res: Response, ctx: Context):
		pass

	def __call__(self, req: Request, ctx: Context, next: Next) -> Response:
		if self.provides is not None:
			ctx.put(self.provides, self.provide(req, ctx))
		res = next(req, ctx)
		self.finish(res, ctx)
		return res


class Thread:
	def __init__(self, middleware: Middleware, next: Next):
		self.middleware = middleware
		self.next = next

	@classmethod
	def build(cls, middlewares: list[Middleware], last: Next) -> Next:
		next = last
		for middleware in reversed(middlewares):
			next = cls(middleware, next)
		return next

	def __call__(self, req: Request, ctx: Any) -> Response:
		return self.middleware(req, ctx, self.next)


class Application:
	def __init__(
		self,
		router: Router,
		components: list[Component[Any]],
	):
		verify(components)
		middlewares: list[Middleware] = [
			ensure_content_length,
			capture_errors,
			manage_resources,
			adapt_artificial_method,
			*components,
			handle_http_errors,
		]
		self.thread = Thread.build(middlewares, router)
		self.components = components

	def boot(self):
		for component in self.components:
			component.boot()

	def handle(self, req: Request) -> Response:
		ctx = Context()
		return self.thread(req, ctx)


def verify(components: list[Component[Any]]):
	provided: set[type[Any]] = set()
	for component in components:
		if not hasattr(component, "provides"):
			raise ComponentError(
				f"{type(component).__qualname__} does not declare what it provides"
			)

		for requirement in component.requires:
			if requirement not in provided:
				raise ComponentError(
					f"{type(component).__qualname__} requires "
					f"{requirement.__qualname__}, which no earlier component provides"
				)

		if component.provides is None:
			continue
		if component.provides in provided:
			raise ComponentError(
				f"more than one component provides {component.provides.__qualname__}"
			)
		provided.add(component.provides)


def manage_resources(req: Request, ctx: Context, next: Next) -> Response:
	with ctx.resources:
		return next(req, ctx)


def ensure_content_length(req: Request, ctx: Context, next: Next) -> Response:
	res = next(req, ctx)
	if "Content-Length" not in res.headers:
		res.headers["Content-Length"] = str(len(str(res.body)))
	return res


def adapt_artificial_method(req: Request, ctx: Context, next: Next) -> Response:
	if "_method" in req.input:
		raw_method = req.input["_method"]
		del req.input["_method"]
		if raw_method == "GET":
			method = Method.GET
		elif raw_method == "POST":
			method = Method.POST
		elif raw_method == "PUT":
			method = Method.PUT
		elif raw_method == "PATCH":
			method = Method.PATCH
		elif raw_method == "DELETE":
			method = Method.DELETE
		req.method = method
	return next(req, ctx)


def capture_errors(req: Request, ctx: Context, next: Next) -> Response:
	try:
		return next(req, ctx)
	except Exception as err:
		import sys
		import traceback

		traceback.print_exception(err, file=sys.stderr)
		return Response.text("500 Internal Server Error", Status.INTERNAL_SERVER_ERROR)


def handle_http_errors(req: Request, ctx: Context, next: Next) -> Response:
	try:
		return next(req, ctx)
	except HTTPError as err:
		return Response.text(f"{err.status}", err.status)
