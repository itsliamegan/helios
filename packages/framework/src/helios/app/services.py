from collections.abc import Callable, Generator, Mapping
from contextlib import ExitStack, contextmanager
from inspect import isgeneratorfunction
from typing import Any, TYPE_CHECKING, cast

from .error import DependencyError

if TYPE_CHECKING:
	from .container import Factory


class Services:
	"""A set of services keyed by type.

	Services are either built by factories or provided at construction. A
	factory may return a service when it is called. A factory may also return a
	generator that yields a service when it is called and cleans up that
	service's resources after it yields.

	A factory that catches an exception raised at its yield without re-raising
	it hides the exception from every factory released after it.
	"""

	def __init__(self, values: Mapping[type[Any], Any] | None = None):
		self.values = dict(values or {})
		self.resources = ExitStack()

	def get[T](self, key: type[T]) -> T | None:
		return cast(T | None, self.values.get(key))

	def build[C, T](self, key: type[T], factory: Factory[C, T], owner: C) -> T:
		if isgeneratorfunction(factory):
			generator = cast(Callable[[C], Generator[T]], factory)
			# Acquire the value from the factory on a temporary stack. Only move
			# the factory's cleanup onto the real stack if it yields a built
			# service. Otherwise, release the factory and raise.
			with ExitStack() as temporary:
				value = temporary.enter_context(contextmanager(generator)(owner))
				if value is None:
					raise DependencyError(
						f"factory for {key.__qualname__} yielded None"
					)
				self.resources.enter_context(temporary.pop_all())
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
		# Release each service in reverse order of acquisition, per ExitStack
		# semantics. If there was an exception, provide it to each yielding
		# factory so that it can tell success from failure. Only an error raised
		# by the cleanup of a yielding factory propagates from here, never this
		# exception.
		if exception is None:
			self.resources.close()
		else:
			self.resources.__exit__(type(exception), exception, exception.__traceback__)
