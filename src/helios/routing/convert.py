from abc import ABC, abstractmethod
from typing import Any
import uuid


class Converter(ABC):
	@abstractmethod
	def convert(self, value: str) -> Any: ...


class Str(Converter):
	def convert(self, value: str) -> str:
		return value


class UUID(Converter):
	def convert(self, value: str) -> uuid.UUID:
		return uuid.UUID(value)


CONVERTERS: dict[str, Converter] = {
	"str": Str(),
	"uuid": UUID(),
}
