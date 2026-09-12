from typing import cast
from urllib.parse import parse_qs, urlsplit
from urllib.parse import urlencode as encode_query

type Query = dict[str, str | list[str]]


class URL:
	def __init__(
		self,
		path: str,
		query: Query | None = None,
		*,
		scheme: str | None = None,
		host: str | None = None,
		port: int | None = None,
	):
		if "://" in path:
			if scheme is not None or host is not None or port is not None:
				raise ValueError("URL components cannot accompany an absolute path")
			parsed = urlsplit(path)
			scheme = parsed.scheme
			host = parsed.hostname
			port = parsed.port
			path = parsed.path
			if query is None:
				query = cast(Query, parse_qs(parsed.query, keep_blank_values=True))

		if (scheme is None) != (host is None):
			raise ValueError("scheme and host must be supplied together")
		if port is not None and host is None:
			raise ValueError("a port requires a host")

		self.scheme = scheme
		self.host = host
		self.port = port
		self.path = path
		self.query = query or {}

	def __str__(self) -> str:
		res = ""
		if self.scheme is not None and self.host is not None:
			res = f"{self.scheme}://{self.host}"
			if self.port is not None:
				res += f":{self.port}"
		res += self.path
		if self.query:
			res += "?" + encode_query(self.query, True)
		return res

	def __repr__(self) -> str:
		args = [repr(self.path), repr(self.query)]
		if self.scheme is not None:
			args.append(f"scheme={self.scheme!r}")
		if self.host is not None:
			args.append(f"host={self.host!r}")
		if self.port is not None:
			args.append(f"port={self.port!r}")
		return f"URL({", ".join(args)})"
