from datetime import datetime
from typing import Any, cast
import uuid


class Type[T]:
	@staticmethod
	def resolve[ValueT](typ: type[ValueT]) -> Type[ValueT]:
		if typ is str:
			return cast(Type[ValueT], Str())
		if typ is bool:
			return cast(Type[ValueT], Bool())
		if typ is int:
			return cast(Type[ValueT], Int())
		if typ is uuid.UUID:
			return cast(Type[ValueT], UUID())
		if typ is datetime:
			return cast(Type[ValueT], Date())
		raise TypeError(f"unsupported attribute type: {typ!r}")

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


class Int(Type[int]):
	def encode(self, val: int) -> Any:
		return val

	def decode(self, val: Any) -> int:
		if isinstance(val, int):
			return val
		else:
			return int(val)


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
