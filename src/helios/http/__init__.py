from enum import Enum

from .cookie import Cookie as Cookie
from .cookie import Cookies as Cookies
from .cookie import SameSite as SameSite
from .file import File as File
from .file import Files as Files
from .headers import Headers
from .url import URL


class Method(Enum):
	GET = "GET"
	POST = "POST"
	PUT = "PUT"
	PATCH = "PATCH"
	DELETE = "DELETE"

	def __repr__(self) -> str:
		return f"Method({self.name!r})"


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

	def __repr__(self) -> str:
		return f"Status({self.code!r}, {self.reason!r})"


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
		return f"Input({self.items!r})"


class Body:
	def __init__(self, content: str | bytes | None = ""):
		self.content = content

	def to_bytes(self) -> bytes:
		if isinstance(self.content, bytes):
			return self.content
		return str(self.content).encode("utf8")

	def __str__(self) -> str:
		return str(self.content)

	def __repr__(self) -> str:
		return f"Body({self.content!r})"


class Request:
	def __init__(
		self,
		method: Method,
		url: URL,
		headers: Headers,
		input: Input,
		files: Files | None = None,
	):
		self.method = method
		self.url = url
		self.headers = headers
		self.input = input
		self.files = files if files is not None else Files()
		self.cookies = Cookies.from_headers(headers)

	@property
	def referrer(self) -> str | None:
		if "Referer" in self.headers:
			return str(self.headers["Referer"])
		else:
			return None

	def __repr__(self) -> str:
		return (
			f"Request({self.method!r}, {self.url!r}, {self.headers!r}, "
			f"{self.input!r}, {self.files!r})"
		)


class Response:
	def __init__(self, status: Status, headers: Headers, cookies: Cookies, body: Body):
		self.status = status
		self.headers = headers
		self.cookies = cookies
		self.body = body

	@classmethod
	def empty(cls, status: Status = Status.NO_CONTENT) -> Response:
		return cls(status, Headers(), Cookies(), Body())

	@classmethod
	def text(cls, text: str, status: Status = Status.OK) -> Response:
		return cls(
			status, Headers({"Content-Type": "text/plain"}), Cookies(), Body(text)
		)

	@classmethod
	def html(cls, html: str, status: Status = Status.OK) -> Response:
		return cls(
			status, Headers({"Content-Type": "text/html"}), Cookies(), Body(html)
		)

	@classmethod
	def file(cls, content: bytes, filename: str, content_type: str) -> Response:
		return cls(
			Status.OK,
			Headers(
				{
					"Content-Type": content_type,
					"Content-Disposition": f'attachment; filename="{filename}"',
					"Content-Length": str(len(content)),
				}
			),
			Cookies(),
			Body(content),
		)

	@classmethod
	def redirect(cls, url: URL) -> Response:
		return cls(Status.FOUND, Headers({"Location": str(url)}), Cookies(), Body())

	def __repr__(self) -> str:
		return f"Response({self.status!r}, {self.headers!r}, {self.body!r})"
