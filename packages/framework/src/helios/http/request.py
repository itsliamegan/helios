from collections.abc import Sequence
from dataclasses import dataclass

from werkzeug.datastructures import MIMEAccept
from werkzeug.http import parse_accept_header

from helios.url import URL

from .cookie import Cookies
from .file import Files
from .header import Headers
from .input import Input
from .method import Method


@dataclass(init=False)
class Request:
	"""An incoming HTTP request.

	Its URL is absolute. Its cookies are parsed from its headers.
	"""

	method: Method
	url: URL
	headers: Headers
	input: Input
	files: Files
	cookies: Cookies

	def __init__(
		self,
		method: Method,
		url: URL,
		headers: Headers | None = None,
		input: Input | None = None,
		files: Files | None = None,
	):
		self.method = method
		self.url = url
		self.headers = headers or Headers()
		self.input = input or Input()
		self.files = files or Files()
		self.cookies = Cookies.from_headers(self.headers)

	@property
	def referrer(self) -> str | None:
		if "Referer" in self.headers:
			return str(self.headers["Referer"])
		else:
			return None

	def prefers(self, types: Sequence[str]) -> str | None:
		"""Return the type in `types` that the client prefers.

		Ties go to the earlier type in `types`. A request without an `Accept`
		header accepts every type.
		"""

		if "Accept" in self.headers:
			accept = parse_accept_header(str(self.headers["Accept"]), MIMEAccept)
		else:
			accept = MIMEAccept([("*/*", 1)])
		return accept.best_match(types)
