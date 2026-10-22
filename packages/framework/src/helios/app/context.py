from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, ExitStack, contextmanager
import inspect
from typing import Any, cast

from helios.http import Request
from helios.http.error import HTTPError

from .container import Container, DependencyError, Scoped, unparameterized


class Context:
	def __init__(self, container: Container, request: Request):
		self.container = container
		self.request = request
		self.scoped: dict[type[Any], Any] = {}
		self.resources = ExitStack()
		self.aborted: HTTPError | None = None

	def get[T](self, key: type[T]) -> T:
		key = unparameterized(key)
		if key is Request:
			return cast(T, self.request)
		if key in self.scoped:
			return cast(T, self.scoped[key])
		binding = self.container.bindings.get(key)
		if binding is None:
			raise DependencyError(f"nothing provides {key.__qualname__}")
		if not isinstance(binding, Scoped):
			return self.container.get(key)

		if inspect.isgeneratorfunction(binding.factory):
			generator = cast(Callable[[Context], Generator[T]], binding.factory)
			# The factory's cleanup runs here if its value is rejected, and
			# moves onto the context's stack once it is accepted.
			with ExitStack() as stack:
				value = stack.enter_context(contextmanager(generator)(self))
				if value is None:
					raise DependencyError(
						f"factory for {key.__qualname__} yielded None"
					)
				self.resources.enter_context(stack.pop_all())
		else:
			factory = cast(Callable[[Context], T], binding.factory)
			value = factory(self)
			if value is None:
				raise DependencyError(f"factory for {key.__qualname__} returned None")
		self.scoped[key] = value
		return value

	def resolved[T](self, key: type[T]) -> T | None:
		key = unparameterized(key)
		if key is Request:
			return cast(T, self.request)
		if key in self.scoped:
			return cast(T, self.scoped[key])
		return self.container.resolved(key)

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)

	def close(self):
		self.resources.close()
