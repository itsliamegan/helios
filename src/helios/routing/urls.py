from typing import Any
from urllib.parse import urlsplit

from helios.http import Method, URL
from helios.http.url import Query

from .router import Match, Router


class URLs:
	def __init__(self, router: Router, base_url: URL):
		if base_url.scheme is None or base_url.host is None:
			raise ValueError("base URL must be absolute")
		self.router = router
		self.base_url = base_url

	def route(
		self,
		name: str,
		params: dict[str, Any] | None = None,
		query: Query | None = None,
		absolute: bool = False,
	) -> URL:
		path = self.router.path(name, params)
		if not absolute:
			return URL(path, query)
		return URL(
			path,
			query,
			scheme=self.base_url.scheme,
			host=self.base_url.host,
			port=self.base_url.port,
		)

	def match(self, url: URL | str | None) -> Match | None:
		if url is None:
			return None
		elif isinstance(url, URL):
			path = url.path
		else:
			try:
				path = urlsplit(url).path
			except ValueError:
				return None
		return self.router.match(Method.GET, URL(path))
