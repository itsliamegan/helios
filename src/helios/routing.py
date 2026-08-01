from collections.abc import Callable
from inspect import signature
import re
from typing import Any, Protocol

from helios.http import Body, Headers, Method, Request, Response, Status, URL

class NotFoundError(Exception):
	pass

class MethodNotAllowedError(Exception):
	pass

class Pattern:
	PARAM_REGEX = re.compile(r"{(\w+)}")

	def __init__(self, raw: str):
		lit = self.PARAM_REGEX.sub(r"(?P<\1>(\\w|-|_)+)", raw)
		if lit.endswith("/"):
			lit += "?$"
		else:
			lit += "/?$"
		self.raw = raw
		self.regex = re.compile(lit)

	def match(self, url: URL) -> dict[str, str] | None:
		match = self.regex.match(url.path)
		if match:
			return match.groupdict()
		else:
			return None

	def __repr__(self) -> str:
		return f"Pattern({repr(self.raw)})"

class Handler(Protocol):
	def __call__(self, req: Request, ctx: Any, params: dict[str, str] | None = None):
		...

class Route:
	def __init__(self, method: Method, pattern: Pattern, handler: Handler):
		self.method = method
		self.pattern = pattern
		self.handler = handler

	def match(self, req: Request) -> dict[str, str] | None:
		if req.method is not self.method:
			return None
		params = self.pattern.match(req.url)
		if params is not None:
			return params
		return None

	def __repr__(self) -> str:
		return f"Route({repr(self.method)}, {repr(self.pattern)}, {repr(self.handler)})"

type Next = Callable[[Request, Any], Response]
type Middleware = Callable[[Request, Any, Next], Response]

class Router:
	def __init__(self, routes: list[Route]):
		self.routes = routes

	def match(self, req: Request) -> tuple[Handler, dict[str, str]] | None:
		for route in self.routes:
			params = route.match(req)
			if params is not None:
				return route.handler, params
		return None

	def __call__(self, req: Request, ctx: Any, next: Next) -> Response:
		match = self.match(req)
		if not match:
			raise NotFoundError()
		handler, params = match
		sig = signature(handler)
		if len(sig.parameters) == 2:
			return handler(req, ctx)
		elif len(sig.parameters) == 3:
			return handler(req, ctx, params)

class Thread:
	def __init__(self, middleware: Middleware, next: Next | None = None):
		self.middleware = middleware
		self.next = next

	@classmethod
	def build(cls, middlewares: list[Middleware]) -> Thread:
		head = None
		tail = None
		for middleware in middlewares:
			link = Thread(middleware)
			if head is None:
				head = link
				tail = link
			else:
				tail.next = link
				tail = link
		return head

	def __call__(self, req: Request, ctx: Any) -> Response:
		return self.middleware(req, ctx, self.next)

class Kernel:
	def __init__(self, routes: list[Route], middlewares: list[Middleware]):
		self.thread = Thread.build([
			*middlewares,
			Router(routes),
		])

	def handle(self, req: Request, ctx: Any) -> Response:
		return self.thread(req, ctx)
