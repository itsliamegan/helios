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
