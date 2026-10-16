from enum import Enum
from typing import Self

from .error import UnsupportedMethodError


class Method(Enum):
	GET = "GET"
	POST = "POST"
	PUT = "PUT"
	PATCH = "PATCH"
	DELETE = "DELETE"

	@classmethod
	def parse(cls, raw: object) -> Self:
		try:
			return cls(raw)
		except ValueError:
			raise UnsupportedMethodError(f"unsupported HTTP method {raw!r}") from None
