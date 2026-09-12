from collections.abc import Callable
import re
from typing import Any, Concatenate
from urllib.parse import quote

from helios.http import Method, Request, Response, URL
from helios.http.error import NotFoundError as BaseNotFoundError
from helios.http.url import Query

from . import convert


class NotFoundError(BaseNotFoundError):
	pass


class MethodNotAllowedError(Exception):
	pass


class RouteNotFoundError(LookupError):
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

	def generate(self, params: dict[str, Any] | None = None) -> str:
		params = params or {}
		expected = set(self.converters)
		supplied = set(params)
		missing = expected - supplied
		unexpected = supplied - expected
		if missing:
			raise ValueError(f"missing route parameters: {", ".join(sorted(missing))}")
		if unexpected:
			raise ValueError(
				f"unexpected route parameters: {", ".join(sorted(unexpected))}"
			)

		def replace(match: re.Match[str]) -> str:
			name = match.group(1)
			value = str(self.converters[name](str(params[name])))
			encoded = quote(value, safe="")
			if re.fullmatch(PARAM_VALUE_REGEX, encoded) is None:
				raise ValueError(f"invalid route parameter: {name}")
			return encoded

		return PARAM_REGEX.sub(replace, self.raw)

	def convert(self, raw_params: dict[str, str]) -> dict[str, Any] | None:
		try:
			params = {}
			for name, value in raw_params.items():
				params[name] = self.converters[name](value)
			return params
		except ValueError:
			return None

	def __repr__(self) -> str:
		return f"Pattern({self.raw!r})"


type Handler[**P] = Callable[Concatenate[Request, Any, P], Response]
type Guard[**P] = Callable[Concatenate[Request, Any, P], Response | None]


class Route:
	def __init__(
		self,
		method: Method,
		pattern: Pattern,
		handler: Handler[...],
		guards: list[Guard[...]] | None = None,
		name: str | None = None,
	):
		self.method = method
		self.pattern = pattern
		self.handler = handler
		self.guards = guards or []
		self.name = name

	def match(self, req: Request) -> dict[str, Any] | None:
		if req.method is not self.method:
			return None
		params = self.pattern.match(req.url)
		if params is not None:
			return params
		return None

	def __repr__(self) -> str:
		return (
			f"Route({self.method!r}, {self.pattern!r}, {self.handler!r}, "
			f"name={self.name!r})"
		)


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
		routes: list[Route] = []
		for item in items:
			if isinstance(item, Group):
				routes.extend(
					cls.flatten(
						item.routes,
						cls.join(prefix, item.prefix),
						[*guards, *item.guards],
					)
				)
			elif prefix or guards:
				routes.append(
					Route(
						item.method,
						Pattern(cls.join(prefix, item.pattern.raw)),
						item.handler,
						[*guards, *item.guards],
						item.name,
					)
				)
			else:
				routes.append(item)
		return routes

	@staticmethod
	def join(prefix: str, pattern: str) -> str:
		if not prefix:
			return pattern
		if not pattern:
			return prefix
		return f"{prefix.rstrip("/")}/{pattern.lstrip("/")}"


class Router:
	def __init__(self, routes: list[Route | Group]):
		self.routes = Group.flatten(routes)
		self.named: dict[str, Route] = {}
		for route in self.routes:
			if route.name is None:
				continue
			if route.name in self.named:
				raise ValueError(f"duplicate route name: {route.name}")
			self.named[route.name] = route

	def path(self, name: str, params: dict[str, Any] | None = None) -> str:
		if name not in self.named:
			raise RouteNotFoundError(f"route not found: {name}")
		return self.named[name].pattern.generate(params)

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


class URLs:
	def __init__(self, router: Router, base_url: URL):
		if base_url.scheme is None or base_url.host is None:
			raise ValueError("base URL must be absolute")
		self.router = router
		self.base_url = base_url

	def route(
		self,
		name: str,
		params: dict[str, Any] | None = None,
		query: Query | None = None,
		*,
		absolute: bool = True,
	) -> URL:
		path = self.router.path(name, params)
		if not absolute:
			return URL(path, query)
		return URL(
			path,
			query,
			scheme=self.base_url.scheme,
			host=self.base_url.host,
			port=self.base_url.port,
		)
