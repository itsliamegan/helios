from dataclasses import dataclass

from .cookie import Cookies
from .file import Files
from .header import Headers
from .input import Input
from .method import Method
from .url import URL


@dataclass(init=False)
class Request:
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
