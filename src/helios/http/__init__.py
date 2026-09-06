from enum import Enum

from .cookie import Cookies
from .headers import Headers
from .url import URL

class Method(Enum):
	GET = "GET"
	POST = "POST"
	PUT = "PUT"
	PATCH = "PATCH"
	DELETE = "DELETE"

	def __repr__(self) -> str:
		return f"Method({repr(self.name)})"

class Status(Enum):
	OK = 200, "OK"
	NO_CONTENT = 204, "No Content"
	FOUND = 302, "Found"
	BAD_REQUEST = 400, "Bad Request"
	FORBIDDEN = 403, "Forbidden"
	NOT_FOUND = 404, "Not Found"
	INTERNAL_SERVER_ERROR = 500, "Internal Server Error"

	def __init__(self, code: int, reason: str):
		self.code = code
		self.reason = reason

	def __str__(self) -> str:
		return f"{self.code} {self.reason}"

	def __repr__(self) -> str:
		return f"Status({repr(self.code)}, {repr(self.reason)})"

class Input:
	def __init__(self, items: dict[str, str | list[str]] | None = None):
		if items is None:
			items = {}
		self.items = items

	def __getitem__(self, name: str) -> str | list[str]:
		return self.items[name]

	def __delitem__(self, name: str):
		del self.items[name]

	def __contains__(self, name: str) -> bool:
		return name in self.items

	def __repr__(self) -> str:
		return f"Input({repr(self.items)})"

class Body:
	def __init__(self, content: str | None = ""):
		self.content = content

	def __str__(self) -> str:
		return str(self.content)

	def __repr__(self) -> str:
		return f"Body({repr(self.content)})"

class Request:
	def __init__(self, method: Method, url: URL, headers: Headers, input: Input):
		self.method = method
		self.url = url
		self.headers = headers
		self.input = input
		self.cookies = Cookies.from_headers(headers)

	@property
	def referrer(self) -> str | None:
		if "Referer" in self.headers:
			return str(self.headers["Referer"])
		else:
			return None

	def __repr__(self) -> str:
		return f"Request({repr(self.method)}, {repr(self.url)}, {repr(self.headers)}, {repr(self.input)})"

class Response:
	def __init__(self, status: Status, headers: Headers, cookies: Cookies, body: Body):
		self.status = status
		self.headers = headers
		self.cookies = cookies
		self.body = body

	@classmethod
	def empty(cls, status: Status = Status.NO_CONTENT) -> "Response":
		return cls(status, Headers(), Cookies(), Body())

	@classmethod
	def text(cls, text: str, status: Status = Status.OK) -> "Response":
		return cls(status, Headers({"Content-Type": "text/plain"}), Cookies(), Body(text))

	@classmethod
	def html(cls, html: str, status: Status = Status.OK) -> "Response":
		return cls(status, Headers({"Content-Type": "text/html"}), Cookies(), Body(html))

	@classmethod
	def redirect(cls, url: URL) -> "Response":
		return cls(Status.FOUND, Headers({"Location": str(url)}), Cookies(), Body())

	def __repr__(self) -> str:
		return f"Response({repr(self.status)}, {repr(self.headers)}, {repr(self.body)})"
