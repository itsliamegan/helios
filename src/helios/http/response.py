from dataclasses import dataclass

from .body import Body
from .cookie import Cookies
from .header import Headers
from .status import Status
from .url import URL


@dataclass
class Response:
	status: Status
	headers: Headers
	cookies: Cookies
	body: Body

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
