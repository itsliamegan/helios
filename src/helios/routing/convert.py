from typing import Any, Protocol
import uuid


class Converter(Protocol):
	def __call__(self, value: str) -> Any: ...


class Str:
	def __call__(self, value: str) -> str:
		return value


class UUID:
	def __call__(self, value: str) -> uuid.UUID:
		return uuid.UUID(value)


CONVERTERS: dict[str, Converter] = {
	"str": Str(),
	"uuid": UUID(),
}
