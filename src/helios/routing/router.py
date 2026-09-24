from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.http import Method, Request, Response, URL
from helios.http.error import NotFoundError

from .route import Group, Route

if TYPE_CHECKING:
	from helios.app import Context


class RouteNotFoundError(LookupError):
	pass


@dataclass
class Match:
	route: Route
	params: dict[str, Any]


class Router:
	def __init__(self, routes: list[Route | Group]):
		self.routes = list(Group(routes))
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
		return self.named[name].pattern.path(params)

	def match(self, method: Method, url: URL) -> Match | None:
		for route in self.routes:
			params = route.match(method, url)
			if params is not None:
				return Match(route, params)
		return None

	def __call__(self, req: Request, ctx: Context) -> Response:
		match = self.match(req.method, req.url)
		if match is None:
			raise NotFoundError()
		return match.route(req, ctx, **match.params)
