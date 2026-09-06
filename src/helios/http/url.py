from urllib.parse import urlencode as encode_query


class URL:
	def __init__(self, path: str, query: dict[str, str | list[str]] | None = None):
		if query is None:
			query = {}
		self.path = path
		self.query = query

	def __str__(self) -> str:
		res = self.path
		if len(self.query) != 0:
			res += "?" + encode_query(self.query, True)
		return res

	def __repr__(self) -> str:
		return f"URL({self.path!r}, {self.query!r})"
