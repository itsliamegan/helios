from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.http import Method, Request, Response
from helios.http.error import NotFoundError
from helios.url import URL

from .route import Group, Route

if TYPE_CHECKING:
	from helios.app import Context


class RouteNotFoundError(LookupError):
	"""Raised when a path is built for a route name that does not exist."""


class Router:
	"""Dispatches each request to the first route that matches it.

	Routes are tried in the order they were declared, so a route with a literal
	segment must come before a route whose parameter would also match it. A
	request that matches no route raises `NotFoundError`. Route names must be
	unique.
	"""

	def __init__(self, routes: Sequence[Route | Group]):
		self.routes = list(Group(routes))
		self.named: dict[str, Route] = {}
		for route in self.routes:
			if route.name is None:
				continue
			if route.name in self.named:
				raise ValueError(f"duplicate route name: {route.name}")
			self.named[route.name] = route

	def path(self, name: str, parameters: Mapping[str, Any] | None = None) -> str:
		if name not in self.named:
			raise RouteNotFoundError(f"route not found: {name}")
		return self.named[name].pattern.path(parameters)

	def match(self, method: Method, url: URL) -> Match | None:
		for route in self.routes:
			parameters = route.match(method, url)
			if parameters is not None:
				return Match(route, parameters)
		return None

	def __call__(self, request: Request, context: Context) -> Response:
		match = self.match(request.method, request.url)
		if match is None:
			raise NotFoundError()
		context.match = match
		return match.route(request, context, **match.parameters)


@dataclass
class Match:
	"""A matched route and its converted parameters."""

	route: Route
	parameters: dict[str, Any]

	def named(self, *patterns: str) -> bool:
		"""Return whether the route's name matches any of `patterns`.

		A pattern is a route name or a prefix followed by `.*`, which matches
		every name under that prefix.
		"""

		for pattern in patterns:
			prefix = pattern.removesuffix(".*")
			if "*" in prefix:
				raise ValueError(f"invalid route name pattern: {pattern}")
			if prefix == "":
				raise ValueError(f"invalid route name pattern: {pattern}")

		name = self.route.name
		if name is None:
			return False

		for pattern in patterns:
			if (
				pattern.endswith(".*") and name.startswith(pattern.removesuffix("*"))
			) or name == pattern:
				return True
		return False
