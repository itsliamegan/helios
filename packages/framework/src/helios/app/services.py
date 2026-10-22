from collections.abc import Callable, Generator, Mapping
from contextlib import ExitStack, contextmanager
from inspect import isgeneratorfunction
from typing import Any, TYPE_CHECKING, cast

from .error import DependencyError

if TYPE_CHECKING:
	from .container import Factory


class Services:
	def __init__(self, values: Mapping[type[Any], Any] | None = None):
		self.values = dict(values or {})
		self.resources = ExitStack()

	def get[T](self, key: type[T]) -> T | None:
		return cast(T | None, self.values.get(key))

	def build[C, T](self, key: type[T], factory: Factory[C, T], owner: C) -> T:
		if isgeneratorfunction(factory):
			generator = cast(Callable[[C], Generator[T]], factory)
			# The factory's cleanup runs here if its value is rejected, and
			# moves onto the services' stack once it is accepted.
			with ExitStack() as stack:
				value = stack.enter_context(contextmanager(generator)(owner))
				if value is None:
					raise DependencyError(
						f"factory for {key.__qualname__} yielded None"
					)
				self.resources.enter_context(stack.pop_all())
		else:
			function = cast(Callable[[C], T], factory)
			value = function(owner)
			if value is None:
				raise DependencyError(f"factory for {key.__qualname__} returned None")
		self.values[key] = value
		return value

	def forget(self, key: type[Any]):
		self.values.pop(key, None)

	def close(self, exception: BaseException | None = None):
		if exception is None:
			self.resources.close()
		else:
			self.resources.__exit__(type(exception), exception, exception.__traceback__)
