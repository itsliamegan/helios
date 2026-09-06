from datetime import datetime
from typing import Any, TypeVar
import uuid

T = TypeVar("T")


class Type[T]:
	def encode(self, val: T) -> Any:
		raise NotImplementedError

	def decode(self, val: Any) -> T:
		raise NotImplementedError


class Str(Type[str]):
	def encode(self, val: str) -> Any:
		return val

	def decode(self, val: Any) -> str:
		if isinstance(val, str):
			return val
		else:
			return str(val)


class Bool(Type[bool]):
	def encode(self, val: bool) -> Any:
		return val

	def decode(self, val: Any) -> bool:
		if isinstance(val, bool):
			return val
		else:
			return bool(val)


class List(Type[list[Any]]):
	def __init__(self, item: Type):
		self.item = item

	def encode(self, val: list[Any]) -> Any:
		encoded = []
		for item in val:
			encoded.append(self.item.encode(item))
		return encoded

	def decode(self, val: Any) -> list[Any]:
		decoded = []
		for item in val:
			decoded.append(self.item.decode(item))
		return decoded


class UUID(Type[uuid.UUID]):
	def encode(self, val: uuid.UUID) -> Any:
		return str(val)

	def decode(self, val: Any) -> uuid.UUID:
		if isinstance(val, uuid.UUID):
			return val
		else:
			return uuid.UUID(val)


class Date(Type[datetime]):
	def encode(self, val: datetime) -> Any:
		return val.isoformat()

	def decode(self, val: Any) -> datetime:
		if isinstance(val, datetime):
			return val
		else:
			return datetime.fromisoformat(val)
