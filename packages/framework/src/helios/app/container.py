from collections.abc import Callable, Generator
from dataclasses import dataclass
from threading import RLock
from typing import Any, TYPE_CHECKING, cast, get_origin

from .error import DependencyError
from .services import Services

if TYPE_CHECKING:
	from .context import Context


class Container:
	def __init__(self):
		self.bindings: dict[type[Any], Binding] = {}
		self.services = Services()
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
		self.services.forget(key)

	def bound(self, key: type[Any]) -> bool:
		return unparameterized(key) in self.bindings

	def binding(self, key: type[Any]) -> Binding:
		key = unparameterized(key)
		binding = self.bindings.get(key)
		if binding is None:
			raise DependencyError(f"nothing provides {key.__qualname__}")
		return binding

	def get[T](self, key: type[T]) -> T:
		if self.closed:
			raise RuntimeError("the container is closed")

		key = unparameterized(key)
		match self.binding(key):
			case Instance(value):
				return cast(T, value)
			case Singleton(factory):
				with self.lock:
					value = self.services.get(key)
					if value is None:
						value = self.services.build(key, factory, self)
					return value
			case Scoped():
				raise DependencyError(f"{key.__qualname__} requires a request context")

	def resolved[T](self, key: type[T]) -> T | None:
		if self.closed:
			raise RuntimeError("the container is closed")

		key = unparameterized(key)
		match self.bindings.get(key):
			case Instance(value):
				return cast(T, value)
			case Singleton():
				with self.lock:
					return self.services.get(key)
			case Scoped() | None:
				return None

	def close(self):
		self.closed = True
		self.services.close()


type Binding = Instance | Singleton | Scoped
type Factory[C, T] = Callable[[C], T] | Callable[[C], Generator[T]]


@dataclass
class Instance:
	value: Any


@dataclass
class Singleton:
	factory: Factory[Container, Any]


@dataclass
class Scoped:
	factory: Factory[Context, Any]


def unparameterized(key: type[Any]) -> type[Any]:
	return get_origin(key) or key
