from collections.abc import Callable
import re
from typing import Any, Concatenate

from helios.http import Method, Request, Response, URL
from helios.http.error import NotFoundError as BaseNotFoundError

from . import convert

class NotFoundError(BaseNotFoundError):
	pass

class MethodNotAllowedError(Exception):
	pass

PARAM_REGEX = re.compile(r"{(\w+)(?::(\w+))?}")
PARAM_VALUE_REGEX = r"[\w-]+"

class Pattern:
	def __init__(self, raw: str):
		self.converters: dict[str, convert.Converter] = {}
		lit = raw
		for param in PARAM_REGEX.finditer(raw):
			name, converter_name = param.groups()
			converter_name = converter_name or "str"
			if converter_name not in convert.CONVERTERS:
				raise ValueError(f"Unknown pattern converter: {converter_name}")
			self.converters[name] = convert.CONVERTERS[converter_name]
			lit = lit.replace(param.group(), f"(?P<{name}>{PARAM_VALUE_REGEX})")

		if lit.endswith("/"):
			lit += "?$"
		else:
			lit += "/?$"
		self.raw = raw
		self.regex = re.compile(lit)

	def match(self, url: URL) -> dict[str, Any] | None:
		match = self.regex.match(url.path)
		if match:
			return self.convert(match.groupdict())
		else:
			return None

	def convert(self, raw_params: dict[str, str]) -> dict[str, Any] | None:
		try:
			params = {}
			for name, value in raw_params.items():
				params[name] = self.converters[name](value)
			return params
		except ValueError:
			return None

	def __repr__(self) -> str:
		return f"Pattern({repr(self.raw)})"

type Handler[**P] = Callable[Concatenate[Request, Any, P], Response]
type Guard[**P] = Callable[Concatenate[Request, Any, P], Response | None]

class Route:
	def __init__(
		self,
		method: Method,
		pattern: Pattern,
		handler: Handler[...],
		guards: list[Guard[...]] | None = None,
	):
		self.method = method
		self.pattern = pattern
		self.handler = handler
		self.guards = guards or []

	def match(self, req: Request) -> dict[str, Any] | None:
		if req.method is not self.method:
			return None
		params = self.pattern.match(req.url)
		if params is not None:
			return params
		return None

	def __repr__(self) -> str:
		return f"Route({repr(self.method)}, {repr(self.pattern)}, {repr(self.handler)})"

class Group:
	def __init__(
		self,
		routes: list[Route | Group],
		prefix: str = "",
		guards: list[Guard[...]] | None = None,
	):
		self.routes = list(routes)
		self.prefix = prefix
		self.guards = guards or []

	@classmethod
	def flatten(
		cls,
		items: list[Route | Group],
		prefix: str = "",
		guards: list[Guard[...]] | None = None,
	) -> list[Route]:
		guards = guards or []
		routes = []
		for item in items:
			if isinstance(item, cls):
				routes.extend(cls.flatten(
					item.routes,
					cls.join(prefix, item.prefix),
					[*guards, *item.guards],
				))
			elif prefix or guards:
				routes.append(Route(
					item.method,
					Pattern(cls.join(prefix, item.pattern.raw)),
					item.handler,
					[*guards, *item.guards],
				))
			else:
				routes.append(item)
		return routes

	@staticmethod
	def join(prefix: str, pattern: str) -> str:
		if not prefix:
			return pattern
		if not pattern:
			return prefix
		return f"{prefix.rstrip('/')}/{pattern.lstrip('/')}"

class Router:
	def __init__(self, routes: list[Route | Group]):
		self.routes = Group.flatten(routes)

	def match(self, req: Request) -> tuple[Route, dict[str, Any]] | None:
		for route in self.routes:
			params = route.match(req)
			if params is not None:
				return route, params
		return None

	def __call__(self, req: Request, ctx: Any) -> Response:
		match = self.match(req)
		if not match:
			raise NotFoundError()
		route, params = match
		for guard in route.guards:
			res = guard(req, ctx, **params)
			if res is not None:
				return res
		return route.handler(req, ctx, **params)
