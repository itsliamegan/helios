from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from typing import Any, cast

from helios.http import Request

from .container import Container, DependencyError, Scoped


class Context:
	def __init__(self, container: Container, request: Request):
		self.container = container
		self.request = request
		self.scoped: dict[type[Any], Any] = {}
		self.resources = ExitStack()
		self.error: Exception | None = None

	def get[T](self, key: type[T]) -> T:
		if key is Request:
			return cast(T, self.request)
		if key in self.scoped:
			return cast(T, self.scoped[key])
		binding = self.container.bindings.get(key)
		if binding is None:
			raise DependencyError(f"nothing provides {key.__qualname__}")
		if not isinstance(binding, Scoped):
			return self.container.resolve(key)

		factory = cast(Callable[[Context], T], binding.factory)
		value = factory(self)
		if value is None:
			raise DependencyError(f"factory for {key.__qualname__} returned None")
		self.scoped[key] = value
		return value

	def resolved[T](self, key: type[T]) -> T | None:
		if key is Request:
			return cast(T, self.request)
		if key in self.scoped:
			return cast(T, self.scoped[key])
		return self.container.resolved(key)

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)

	def close(self):
		self.resources.close()
