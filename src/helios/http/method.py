from enum import Enum


class UnsupportedMethodError(ValueError):
	pass


class Method(Enum):
	GET = "GET"
	POST = "POST"
	PUT = "PUT"
	PATCH = "PATCH"
	DELETE = "DELETE"

	@classmethod
	def parse(cls, raw: object) -> Method:
		try:
			return cls(raw)
		except ValueError:
			raise UnsupportedMethodError(f"unsupported HTTP method {raw!r}") from None
