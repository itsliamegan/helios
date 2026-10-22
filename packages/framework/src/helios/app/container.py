from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import inspect
from threading import RLock
from typing import Any, TYPE_CHECKING, cast, get_origin

if TYPE_CHECKING:
	from .context import Context


class DependencyError(Exception):
	pass


@dataclass
class Instance:
	value: Any


@dataclass
class Singleton:
	factory: Factory[Container, Any]


@dataclass
class Scoped:
	factory: Factory[Context, Any]


type Binding = Instance | Singleton | Scoped
type Factory[C, T] = Callable[[C], T] | Callable[[C], Generator[T]]


class Container:
	def __init__(self):
		self.bindings: dict[type[Any], Binding] = {}
		self.singletons: dict[type[Any], Any] = {}
		self.resources = ExitStack()
		self.lock = RLock()
		self.closed = False

	def instance[T](self, key: type[T], value: T):
		self.register(key, Instance(value))

	def singleton[T](self, key: type[T], factory: Factory[Container, T]):
		self.register(key, Singleton(factory))

	def scoped[T](self, key: type[T], factory: Factory[Context, T]):
		self.register(key, Scoped(factory))

	def register(self, key: type[Any], binding: Binding):
		key = unparameterized(key)
		if isinstance(binding, Instance) and binding.value is None:
			raise DependencyError(f"{key.__qualname__} cannot be bound to None")
		self.bindings[key] = binding
		self.singletons.pop(key, None)

	def bound(self, key: type[Any]) -> bool:
		return unparameterized(key) in self.bindings

	def get[T](self, key: type[T]) -> T:
		if self.closed:
			raise RuntimeError("the container is closed")

		key = unparameterized(key)
		binding = self.bindings.get(key)
		if binding is None:
			raise DependencyError(f"nothing provides {key.__qualname__}")
		if isinstance(binding, Scoped):
			raise DependencyError(f"{key.__qualname__} requires a request context")
		if isinstance(binding, Instance):
			return cast(T, binding.value)

		with self.lock:
			if key in self.singletons:
				return cast(T, self.singletons[key])
			if inspect.isgeneratorfunction(binding.factory):
				generator = cast(Callable[[Container], Generator[T]], binding.factory)
				# The factory's cleanup runs here if its value is rejected, and
				# moves onto the container's stack once it is accepted.
				with ExitStack() as stack:
					value = stack.enter_context(contextmanager(generator)(self))
					if value is None:
						raise DependencyError(
							f"factory for {key.__qualname__} yielded None"
						)
					self.resources.enter_context(stack.pop_all())
			else:
				factory = cast(Callable[[Container], T], binding.factory)
				value = factory(self)
				if value is None:
					raise DependencyError(
						f"factory for {key.__qualname__} returned None"
					)
			self.singletons[key] = value
			return value

	def resolved[T](self, key: type[T]) -> T | None:
		if self.closed:
			raise RuntimeError("the container is closed")

		key = unparameterized(key)
		binding = self.bindings.get(key)
		if binding is None or isinstance(binding, Scoped):
			return None
		if isinstance(binding, Instance):
			return cast(T, binding.value)
		with self.lock:
			return cast(T | None, self.singletons.get(key))

	def close(self):
		self.closed = True
		self.resources.close()


def unparameterized(key: type[Any]) -> type[Any]:
	return get_origin(key) or key
