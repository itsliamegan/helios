from collections.abc import Iterable
from dataclasses import dataclass, field

from .body import Body, Buffered, Stream
from .cookie import Cookies
from .header import Headers
from .status import Status
from .url import URL


@dataclass
class Response:
	status: Status = Status.OK
	headers: Headers = field(default_factory=Headers)
	cookies: Cookies = field(default_factory=Cookies)
	body: Body = field(default_factory=Buffered)

	@classmethod
	def empty(cls, status: Status = Status.NO_CONTENT) -> Response:
		return cls(status)

	@classmethod
	def text(cls, text: str, status: Status = Status.OK) -> Response:
		return cls(status, Headers({"Content-Type": "text/plain"}), body=Buffered(text))

	@classmethod
	def html(cls, html: str, status: Status = Status.OK) -> Response:
		return cls(status, Headers({"Content-Type": "text/html"}), body=Buffered(html))

	@classmethod
	def file(cls, content: bytes, filename: str, content_type: str) -> Response:
		headers = Headers(
			{
				"Content-Type": content_type,
				"Content-Disposition": f'attachment; filename="{filename}"',
				"Content-Length": str(len(content)),
			}
		)
		return cls(Status.OK, headers, body=Buffered(content))

	@classmethod
	def redirect(cls, url: URL) -> Response:
		return cls(Status.FOUND, Headers({"Location": str(url)}))

	@classmethod
	def stream(
		cls,
		chunks: Iterable[bytes],
		status: Status = Status.OK,
		content_type: str = "text/event-stream",
	) -> Response:
		return cls(status, Headers({"Content-Type": content_type}), body=Stream(chunks))
