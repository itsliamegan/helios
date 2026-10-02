from abc import ABC, abstractmethod
from typing import Any
import uuid


class Converter[T](ABC):
	@classmethod
	def for_name(cls, name: str) -> Converter[Any] | None:
		return CONVERTERS.get(name)

	@abstractmethod
	def convert(self, value: str) -> T: ...

	@abstractmethod
	def format(self, value: T) -> str: ...

	def __repr__(self) -> str:
		return f"{type(self).__name__}()"


class Str(Converter[str]):
	def convert(self, value: str) -> str:
		return value

	def format(self, value: str) -> str:
		return str(value)


class UUID(Converter[uuid.UUID]):
	def convert(self, value: str) -> uuid.UUID:
		return uuid.UUID(value)

	def format(self, value: uuid.UUID) -> str:
		return str(uuid.UUID(str(value)))


CONVERTERS: dict[str, Converter[Any]] = {
	"str": Str(),
	"uuid": UUID(),
}
