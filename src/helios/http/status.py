from enum import Enum


class Status(Enum):
	OK = 200, "OK"
	NO_CONTENT = 204, "No Content"
	FOUND = 302, "Found"
	BAD_REQUEST = 400, "Bad Request"
	FORBIDDEN = 403, "Forbidden"
	NOT_FOUND = 404, "Not Found"
	TOO_MANY_REQUESTS = 429, "Too Many Requests"
	INTERNAL_SERVER_ERROR = 500, "Internal Server Error"

	def __init__(self, code: int, reason: str):
		self.code = code
		self.reason = reason

	def __str__(self) -> str:
		return f"{self.code} {self.reason}"
