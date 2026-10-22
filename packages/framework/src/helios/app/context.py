from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
import inspect
from typing import Any, Self, cast

from helios.http import Request

from .container import Container, DependencyError, Scoped, unparameterized


class Context:
	def __init__(self, container: Container, request: Request):
		self.container = container
		self.request = request
		self.scoped: dict[type[Any], Any] = {}
		self.resources = ExitStack()
		self.failure: Exception | None = None
		self.closed = False

	def get[T](self, key: type[T]) -> T:
		if self.closed:
			raise RuntimeError("the context is closed")

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
		if self.closed:
			raise RuntimeError("the context is closed")

		key = unparameterized(key)
		if key is Request:
			return cast(T, self.request)
		if key in self.scoped:
			return cast(T, self.scoped[key])
		return self.container.resolved(key)

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exception_type, exception, traceback):
		self.closed = True
		if exception is not None:
			self.resources.__exit__(exception_type, exception, traceback)
		elif self.failure is not None:
			# The failure is raised into each yielding factory so it can tell
			# success from failure. Its response is already rendered, so the
			# failure itself goes no further.
			self.resources.__exit__(
				type(self.failure),
				self.failure,
				self.failure.__traceback__,
			)
		else:
			self.resources.close()
		return False
