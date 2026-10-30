from typing import Self

from helios.http import Request
from helios.routing import Match

from .container import Container, Instance, Scoped, Singleton, unparameterized
from .services import Services


class Context:
	"""A set of services scoped to a single request.

	The context includes the current request. It builds each scoped service once
	and releases it when its with block ends. Lookups of any other service
	delegate to the container, so an application service can be resolved
	through the context.

	The context records the match the router dispatched to and the first error
	the kernel encountered as the request's failure.
	"""

	def __init__(self, container: Container, request: Request):
		self.container = container
		self.request = request
		self.services = Services({Request: request})
		self.match: Match | None = None
		self.failure: Exception | None = None
		self.closed = False

	def get[T](self, key: type[T]) -> T:
		if self.closed:
			raise RuntimeError("the context is closed")

		key = unparameterized(key)
		value = self.services.get(key)
		if value is not None:
			return value

		match self.container.binding(key):
			case Instance() | Singleton():
				return self.container.get(key)
			case Scoped(factory):
				return self.services.build(key, factory, self)

	def resolved[T](self, key: type[T]) -> T | None:
		if self.closed:
			raise RuntimeError("the context is closed")

		key = unparameterized(key)
		value = self.services.get(key)
		if value is not None:
			return value
		return self.container.resolved(key)

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exception_type, exception, traceback):
		self.closed = True
		# An exception that escaped the block takes precedence over a recorded
		# failure.
		self.services.close(exception or self.failure)
		return False
