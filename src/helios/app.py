from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from enum import Enum
from typing import Any, cast

from helios.http import Method, Request, Response, Status, URL
from helios.http.error import HTTPError
from helios.routing import Router, URLs

type Next = Callable[[Request, Any], Response]
type Middleware = Callable[[Request, Any, Next], Response]


class Context:
	def __init__(self, parent: Context | None = None):
		self.parent = parent
		self.provided: dict[type[Any], Any] = {}
		self.resources = ExitStack()

	def get[T](self, key: type[T]) -> T:
		if key in self.provided:
			return cast(T, self.provided[key])
		if self.parent is not None:
			return self.parent.get(key)
		raise ComponentError(f"nothing provides {key.__qualname__}")

	def put[T](self, key: type[T], val: T):
		self.provided[key] = val

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)


class ComponentError(Exception):
	pass


class Lifetime(Enum):
	APPLICATION = "application"
	REQUEST = "request"


class Config:
	def __init__(self, base_url: URL | None = None):
		self.base_url = base_url


class Component[T]:
	lifetime = Lifetime.REQUEST
	provides: type[T] | None
	requires: tuple[type[Any], ...] = ()

	def boot(self):
		pass

	def provide(self, ctx: Context) -> T:
		raise NotImplementedError

	def finish(self, res: Response, ctx: Context):
		pass

	def __call__(self, req: Request, ctx: Context, next: Next) -> Response:
		if self.provides is not None:
			ctx.put(self.provides, self.provide(ctx))
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
		config: Config,
		router: Router,
		components: list[Component[Any]],
		middlewares: list[Middleware] | None = None,
	):
		self.context = Context()
		self.context.put(Router, router)
		if config.base_url is not None:
			self.context.put(URLs, URLs(router, config.base_url))
		provided = verify(components, set(self.context.provided))
		middlewares = middlewares or []
		verify_middlewares(middlewares, provided)
		request_components = [
			component
			for component in components
			if component.lifetime is Lifetime.REQUEST
		]
		thread: list[Middleware] = [
			ensure_content_length,
			capture_errors,
			manage_resources,
			adapt_artificial_method,
			*request_components,
			handle_http_errors,
			*middlewares,
		]
		self.thread = Thread.build(thread, router)
		self.components = components

	def boot(self):
		for component in self.components:
			component.boot()
			if (
				component.lifetime is Lifetime.APPLICATION
				and component.provides is not None
			):
				self.context.put(component.provides, component.provide(self.context))

	def handle(self, req: Request) -> Response:
		ctx = Context(self.context)
		ctx.put(Request, req)
		return self.thread(req, ctx)


def verify(
	components: list[Component[Any]],
	application_provided: set[type[Any]] | None = None,
):
	application_provided = application_provided or set()
	request_provided = {*application_provided, Request}
	provided = set(request_provided)
	for component in components:
		if not hasattr(component, "provides"):
			raise ComponentError(
				f"{type(component).__qualname__} does not declare what it provides"
			)

		available = (
			application_provided
			if component.lifetime is Lifetime.APPLICATION
			else request_provided
		)
		for requirement in component.requires:
			if requirement not in available:
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
		if component.lifetime is Lifetime.APPLICATION:
			application_provided.add(component.provides)
		request_provided.add(component.provides)
	return provided


def verify_middlewares(
	middlewares: list[Middleware],
	provided: set[type[Any]],
):
	for middleware in middlewares:
		for requirement in getattr(middleware, "requires", ()):
			if requirement not in provided:
				raise ComponentError(
					f"{type(middleware).__qualname__} requires "
					f"{requirement.__qualname__}, which no component provides"
				)


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
