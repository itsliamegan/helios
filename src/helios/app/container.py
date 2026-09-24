from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from threading import RLock
from typing import Any, TYPE_CHECKING, cast

if TYPE_CHECKING:
	from .context import Context


class DependencyError(Exception):
	pass


class Binding:
	pass


@dataclass
class Instance(Binding):
	value: Any


@dataclass
class Singleton(Binding):
	factory: Callable[[Container], Any]


@dataclass
class Scoped(Binding):
	factory: Callable[[Context], Any]


class Container:
	def __init__(self):
		self.bindings: dict[type[Any], Binding] = {}
		self.singletons: dict[type[Any], Any] = {}
		self.resources = ExitStack()
		self.lock = RLock()

	def instance[T](self, key: type[T], value: T):
		self.register(key, Instance(value))

	def singleton[T](self, key: type[T], factory: Callable[[Container], T]):
		self.register(key, Singleton(factory))

	def scoped[T](self, key: type[T], factory: Callable[[Context], T]):
		self.register(key, Scoped(factory))

	def register(self, key: type[Any], binding: Binding):
		if isinstance(binding, Instance) and binding.value is None:
			raise DependencyError(f"{key.__qualname__} cannot be bound to None")
		self.bindings[key] = binding
		self.singletons.pop(key, None)

	def bound(self, key: type[Any]) -> bool:
		return key in self.bindings

	def get[T](self, key: type[T]) -> T:
		return self.resolve(key)

	def resolve[T](self, key: type[T]) -> T:
		binding = self.bindings.get(key)
		if binding is None:
			raise DependencyError(f"nothing provides {key.__qualname__}")
		if isinstance(binding, Scoped):
			raise DependencyError(f"{key.__qualname__} requires a request context")
		if isinstance(binding, Instance):
			return cast(T, binding.value)

		singleton = cast(Singleton, binding)
		with self.lock:
			if key in self.singletons:
				return cast(T, self.singletons[key])
			factory = cast(Callable[[Container], T], singleton.factory)
			value = factory(self)
			if value is None:
				raise DependencyError(f"factory for {key.__qualname__} returned None")
			self.singletons[key] = value
			return value

	def resolved[T](self, key: type[T]) -> T | None:
		binding = self.bindings.get(key)
		if binding is None or isinstance(binding, Scoped):
			return None
		if isinstance(binding, Instance):
			return cast(T, binding.value)
		with self.lock:
			return cast(T | None, self.singletons.get(key))

	def enter[T](self, resource: AbstractContextManager[T]) -> T:
		return self.resources.enter_context(resource)

	def close(self):
		self.resources.close()
