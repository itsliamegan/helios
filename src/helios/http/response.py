from collections.abc import Iterable
from dataclasses import dataclass

from .body import Body, Buffered, Stream
from .cookie import Cookies
from .header import Headers
from .status import Status
from .url import URL


@dataclass(init=False)
class Response:
	status: Status
	headers: Headers
	cookies: Cookies
	body: Body

	def __init__(
		self,
		status: Status = Status.OK,
		headers: Headers | None = None,
		cookies: Cookies | None = None,
		body: Body | None = None,
	):
		self.status = status
		self.headers = headers or Headers()
		self.cookies = cookies or Cookies()
		self.body = body or Buffered()

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
		return cls(
			Status.OK,
			Headers(
				{
					"Content-Type": content_type,
					"Content-Disposition": f'attachment; filename="{filename}"',
					"Content-Length": str(len(content)),
				}
			),
			body=Buffered(content),
		)

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
