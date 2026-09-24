from collections.abc import Callable, Iterator
from typing import Any, Concatenate, TYPE_CHECKING

from helios.http import Method, Request, Response, URL

from .pattern import Pattern, join

if TYPE_CHECKING:
	from helios.app import Context

type Handler[**P] = Callable[Concatenate[Request, Context, P], Response]
type Guard[**P] = Callable[Concatenate[Request, Context, P], Response | None]


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

	def within(self, prefix: str, guards: list[Guard[...]]) -> Route:
		if not prefix and not guards:
			return self
		return Route(
			self.method,
			self.pattern.prefixed(prefix),
			self.handler,
			[*guards, *self.guards],
			self.name,
		)

	def match(self, method: Method, url: URL) -> dict[str, Any] | None:
		if method is not self.method:
			return None
		return self.pattern.match(url)

	def __call__(self, req: Request, ctx: Context, **params: Any) -> Response:
		for guard in self.guards:
			res = guard(req, ctx, **params)
			if res is not None:
				return res
		return self.handler(req, ctx, **params)

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

	def within(self, prefix: str, guards: list[Guard[...]]) -> Group:
		return Group(self.routes, join(prefix, self.prefix), [*guards, *self.guards])

	def __iter__(self) -> Iterator[Route]:
		for item in self.routes:
			if isinstance(item, Group):
				yield from item.within(self.prefix, self.guards)
			else:
				yield item.within(self.prefix, self.guards)
