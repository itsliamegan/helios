from typing import Self
from urllib.parse import urlsplit

from .query import Query


class URL:
	def __init__(
		self,
		path: str,
		query: Query | None = None,
		*,
		scheme: str | None = None,
		user: str | None = None,
		password: str | None = None,
		host: str | None = None,
		port: int | None = None,
		fragment: str | None = None,
	):
		if (scheme is None) != (host is None):
			raise ValueError("scheme and host must be supplied together")
		if host is not None and not URL.is_valid_host(host):
			raise ValueError(f"invalid host {host!r}")
		if port is not None and host is None:
			raise ValueError("a port requires a host")
		if user is not None and host is None:
			raise ValueError("a user requires a host")
		if password is not None and user is None:
			raise ValueError("a password requires a user")
		if path and not path.startswith("/"):
			raise ValueError("a path must be empty or start with /")

		self.scheme = scheme
		self.user = user
		self.password = password
		self.host = host
		self.port = port
		self.path = path
		self.query = query or Query()
		self.fragment = fragment

	@classmethod
	def parse(cls, raw: str) -> Self:
		parts = urlsplit(raw)
		if parts.scheme and not parts.netloc:
			raise ValueError(f"absolute URL has no host: {raw!r}")
		if parts.netloc and not parts.scheme:
			raise ValueError(f"URL has a host but no scheme: {raw!r}")

		if parts.netloc:
			userinfo, _, address = parts.netloc.rpartition("@")
			if address.startswith("["):
				host = address[: address.index("]") + 1]
			else:
				host = address.partition(":")[0]
		else:
			userinfo, host = "", None

		if userinfo:
			user, has_password, password = userinfo.partition(":")
			password = password if has_password else None
		else:
			user, password = None, None

		return cls(
			parts.path,
			Query.parse(parts.query),
			scheme=parts.scheme or None,
			user=user,
			password=password,
			host=host,
			port=parts.port,
			fragment=parts.fragment or None,
		)

	@staticmethod
	def is_valid_host(host: str) -> bool:
		if not host:
			return False
		for char in host:
			if char.isspace() or not char.isprintable():
				return False
		return True

	def __str__(self) -> str:
		res = ""
		if self.scheme is not None and self.host is not None:
			res = f"{self.scheme}://"
			if self.user is not None:
				res += self.user
				if self.password is not None:
					res += f":{self.password}"
				res += "@"
			res += self.host
			if self.port is not None:
				res += f":{self.port}"
		res += self.path
		if self.query.text:
			res += f"?{self.query}"
		if self.fragment is not None:
			res += f"#{self.fragment}"
		return res

	def __repr__(self) -> str:
		args = [repr(self.path), repr(self.query)]
		if self.scheme is not None:
			args.append(f"scheme={self.scheme!r}")
		if self.user is not None:
			args.append(f"user={self.user!r}")
		if self.password is not None:
			args.append(f"password={self.password!r}")
		if self.host is not None:
			args.append(f"host={self.host!r}")
		if self.port is not None:
			args.append(f"port={self.port!r}")
		if self.fragment is not None:
			args.append(f"fragment={self.fragment!r}")
		return f"URL({", ".join(args)})"
