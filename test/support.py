from typing import Any, cast

from helios.persist import Handle, JSONFile


class MemoryHandle[T]:
	def __init__(self, value: T):
		self.value = value
		self.saved: T | None = None

	def load(self) -> T:
		return self.value

	def save(self, value: T) -> None:
		self.saved = value
		self.value = value


class MemoryPersistence:
	def __init__(self, value: Any):
		self.handle = MemoryHandle(value)

	def open[T](self, file: JSONFile[T]) -> Handle[T]:
		return cast(Handle[T], self.handle)
