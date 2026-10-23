from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from helios.url import URL

from . import sse
from .body import Body, Buffered, Stream
from .cookie import Cookies
from .error import HTTPError
from .header import Headers
from .status import Status


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
	def empty(cls, status: Status = Status.NO_CONTENT) -> Self:
		return cls(status)

	@classmethod
	def text(cls, text: str, status: Status = Status.OK) -> Self:
		return cls(status, Headers({"Content-Type": "text/plain"}), body=Buffered(text))

	@classmethod
	def html(cls, html: str, status: Status = Status.OK) -> Self:
		return cls(status, Headers({"Content-Type": "text/html"}), body=Buffered(html))

	@classmethod
	def error(cls, error: HTTPError) -> Self:
		return cls.text(f"{error.status}", error.status)

	@classmethod
	def file(cls, content: bytes, filename: str, content_type: str) -> Self:
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
	def redirect(cls, url: URL) -> Self:
		return cls(Status.FOUND, Headers({"Location": str(url)}))

	@classmethod
	def stream(
		cls,
		chunks: Iterable[bytes],
		content_type: str,
		status: Status = Status.OK,
	) -> Self:
		return cls(status, Headers({"Content-Type": content_type}), body=Stream(chunks))

	@classmethod
	def event_stream(cls, items: Iterable[sse.Event | sse.Comment]) -> Self:
		"""Stream server-sent events and comments.

		The request context closes before the server reads the stream, so a
		generator passed here runs after its handler has returned. Acquire
		resources the stream owns, such as a subscription, inside the
		generator's body, so that they are acquired only once delivery starts
		and released when the server closes the stream. Use a short database
		transaction for each operation rather than one held across a `yield`,
		because a transaction holds the database's write lock.
		"""
		response = cls.stream(sse.encode(items), "text/event-stream; charset=utf-8")
		response.headers["Cache-Control"] = "no-cache"
		return response
