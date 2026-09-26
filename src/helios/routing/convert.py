from abc import ABC, abstractmethod
from typing import Any
import uuid


class Converter(ABC):
	@abstractmethod
	def convert(self, value: str) -> Any: ...

	@abstractmethod
	def format(self, value: Any) -> str: ...


class Str(Converter):
	def convert(self, value: str) -> str:
		return value

	def format(self, value: Any) -> str:
		return str(value)


class UUID(Converter):
	def convert(self, value: str) -> uuid.UUID:
		return uuid.UUID(value)

	def format(self, value: Any) -> str:
		return str(uuid.UUID(str(value)))


CONVERTERS: dict[str, Converter] = {
	"str": Str(),
	"uuid": UUID(),
}
