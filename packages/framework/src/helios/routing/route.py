from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Concatenate, Self, TYPE_CHECKING

from helios.http import Method, Request, Response
from helios.url import Pattern, URL

if TYPE_CHECKING:
	from helios.app import Context

# A handler takes the request, its context, and the route's parameters by name.
type Handler[**P] = Callable[Concatenate[Request, Context, P], Response]

# A guard takes the request, its context, and the route's parameters by name.
# Returning a response answers the request in place of the handler, and
# returning `None` lets the request through.
type Guard[**P] = Callable[Concatenate[Request, Context, P], Response | None]


@dataclass(init=False)
class Route:
	"""A response handler matched to a method and path pattern.

	Calling a route runs its guards in order and then its handler unless a
	guard answers the request first.
	"""

	method: Method
	pattern: Pattern
	handler: Handler[...]
	guards: Sequence[Guard[...]]
	name: str | None

	def __init__(
		self,
		method: Method,
		pattern: Pattern,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	):
		self.method = method
		self.pattern = pattern
		self.handler = handler
		self.guards = guards or []
		self.name = name

	@classmethod
	def get(
		cls,
		pattern: str,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	) -> Self:
		return cls(Method.GET, Pattern.parse(pattern), handler, guards, name)

	@classmethod
	def post(
		cls,
		pattern: str,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	) -> Self:
		return cls(Method.POST, Pattern.parse(pattern), handler, guards, name)

	@classmethod
	def put(
		cls,
		pattern: str,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	) -> Self:
		return cls(Method.PUT, Pattern.parse(pattern), handler, guards, name)

	@classmethod
	def patch(
		cls,
		pattern: str,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	) -> Self:
		return cls(Method.PATCH, Pattern.parse(pattern), handler, guards, name)

	@classmethod
	def delete(
		cls,
		pattern: str,
		handler: Handler[...],
		guards: Sequence[Guard[...]] | None = None,
		name: str | None = None,
	) -> Self:
		return cls(Method.DELETE, Pattern.parse(pattern), handler, guards, name)

	def within(self, prefix: Pattern, guards: Sequence[Guard[...]]) -> Route:
		"""Return this route under a prefix, with `guards` running before its own."""

		pattern = self.pattern.prefixed(prefix)
		if pattern == self.pattern and not guards:
			return self
		return Route(
			self.method,
			pattern,
			self.handler,
			[*guards, *self.guards],
			self.name,
		)

	def match(self, method: Method, url: URL) -> dict[str, Any] | None:
		if method is not self.method:
			return None
		return self.pattern.match(url)

	def __call__(
		self, request: Request, context: Context, **parameters: Any
	) -> Response:
		for guard in self.guards:
			response = guard(request, context, **parameters)
			if response is not None:
				return response
		return self.handler(request, context, **parameters)


@dataclass(init=False)
class Group:
	"""Routes and groups that share a path prefix and guards.

	A group's guards run before those of everything inside it. Iterating a group
	flattens it into routes in the order they were declared.
	"""

	routes: list[Route | Group]
	prefix: Pattern
	guards: Sequence[Guard[...]]

	def __init__(
		self,
		routes: Sequence[Route | Group],
		prefix: str = "",
		guards: Sequence[Guard[...]] | None = None,
	):
		self.routes = list(routes)
		self.prefix = Pattern.parse(prefix)
		self.guards = guards or []

	def within(self, prefix: Pattern, guards: Sequence[Guard[...]]) -> Iterator[Route]:
		prefix = self.prefix.prefixed(prefix)
		guards = [*guards, *self.guards]
		for item in self.routes:
			if isinstance(item, Group):
				yield from item.within(prefix, guards)
			else:
				yield item.within(prefix, guards)

	def __iter__(self) -> Iterator[Route]:
		return self.within(Pattern(()), [])
