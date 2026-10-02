from collections.abc import Mapping, Sequence
from typing import Any

from helios.http import Method, Query, URL

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
		params: Mapping[str, Any] | None = None,
		query: Query | Mapping[str, str | Sequence[str]] | None = None,
		absolute: bool = False,
	) -> URL:
		path = self.router.path(name, params)
		if isinstance(query, Mapping):
			query = Query(query)
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
		elif isinstance(url, str):
			try:
				url = URL.parse(url)
			except ValueError:
				return None
		return self.router.match(Method.GET, url)
