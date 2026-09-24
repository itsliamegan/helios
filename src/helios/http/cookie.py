from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from werkzeug.http import dump_cookie, parse_cookie

from .header import Headers

type SameSite = Literal["Lax", "Strict", "None"]


@dataclass
class Cookie:
	name: str
	value: str
	path: str = "/"
	expires: datetime | None = None
	http_only: bool = False
	secure: bool = False
	same_site: SameSite | None = None

	def __setattr__(self, name: str, value: object):
		if name == "same_site" and value not in (None, "Lax", "Strict", "None"):
			raise ValueError(f"unsupported SameSite value: {value!r}")
		super().__setattr__(name, value)

	def __str__(self) -> str:
		return dump_cookie(
			self.name,
			self.value,
			path=self.path,
			expires=self.expires,
			secure=self.secure,
			httponly=self.http_only,
			samesite=self.same_site,
		)


@dataclass(init=False)
class Cookies:
	cookies: dict[str, Cookie]

	def __init__(self, pairs: dict[str, str] | None = None):
		if pairs is None:
			pairs = {}
		cookies = {}
		for name in pairs:
			cookies[name] = Cookie(name, pairs[name])
		self.cookies = cookies

	@classmethod
	def from_headers(cls, headers: Headers) -> Cookies:
		cookies = cls()
		if "Cookie" not in headers:
			return cookies
		for name, value in parse_cookie(str(headers["Cookie"])).items():
			cookies[name] = value
		return cookies

	def to_headers(self) -> Headers:
		headers = Headers()
		if len(self.cookies) > 0:
			headers["Set-Cookie"] = []
			for name in self.cookies:
				headers["Set-Cookie"] += str(self.cookies[name])
		return headers

	def __getitem__(self, name: str) -> Cookie:
		return self.cookies[name]

	def __setitem__(self, name: str, value: str | Cookie):
		if isinstance(value, Cookie):
			self.cookies[name] = value
		elif name in self.cookies:
			self.cookies[name].value = value
		else:
			self.cookies[name] = Cookie(name, value)

	def __contains__(self, name: str) -> bool:
		return name in self.cookies
