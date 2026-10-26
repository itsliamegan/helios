from collections.abc import Mapping, Sequence
from typing import Any

from helios.http import Method
from helios.url import Query, URL

from .router import Match, Router


class URLs:
	"""Builds URLs for named routes and matches URLs back to routes.

	A built URL is relative unless it is requested as absolute, in which case
	it takes the scheme, host, and port of the base URL.
	"""

	def __init__(self, router: Router, base_url: URL):
		if base_url.scheme is None or base_url.host is None:
			raise ValueError("base URL must be absolute")
		self.router = router
		self.base_url = base_url

	def route(
		self,
		name: str,
		parameters: Mapping[str, Any] | None = None,
		query: Query | Mapping[str, str | Sequence[str]] | None = None,
		absolute: bool = False,
	) -> URL:
		path = self.router.path(name, parameters)
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
		"""Match a URL's path to a `GET` route.

		Text that does not parse as a URL matches nothing.
		"""

		if url is None:
			return None
		elif isinstance(url, str):
			try:
				url = URL.parse(url)
			except ValueError:
				return None
		return self.router.match(Method.GET, url)
