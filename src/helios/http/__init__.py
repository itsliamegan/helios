from .cookie import Cookies
from .headers import Headers
from .url import URL

class Method:
	def __init__(self, name: str):
		self.name = name

	def __repr__(self):
		return f"Method({repr(self.name)})"

Method.GET = Method("GET")
Method.POST = Method("POST")
Method.PUT = Method("PUT")
Method.PATCH = Method("PATCH")
Method.DELETE = Method("DELETE")

class Status:
	def __init__(self, code: int, reason: str):
		self.code = code
		self.reason = reason

	def __str__(self) -> str:
		return f"{self.code} {self.reason}"

	def __repr__(self) -> str:
		return f"Status({repr(self.code)}, {repr(self.reason)})"

Status.OK = Status(200, "OK")
Status.NO_CONTENT = Status(204, "No Content")
Status.FOUND = Status(302, "Found")
Status.BAD_REQUEST = Status(400, "Bad Request")
Status.NOT_FOUND = Status(404, "Not Found")
Status.INTERNAL_SERVER_ERROR = Status(500, "Internal Server Error")

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

	def __repr__(self) -> str:
		return f"Request({repr(self.method)}, {repr(self.url)}, {repr(self.headers)}, {repr(self.input)})"

class Response:
	def __init__(self, status: Status, headers: Headers, cookies: Cookies, body: Body):
		self.status = status
		self.headers = headers
		self.cookies = cookies
		self.body = body

	@classmethod
	def empty(cls, status = Status.NO_CONTENT) -> "Response":
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
