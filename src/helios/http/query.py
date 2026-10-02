from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode


@dataclass(init=False)
class Query:
	text: str

	def __init__(self, items: Mapping[str, str | list[str]] | None = None):
		items = items or {}
		self.text = urlencode(items, doseq=True)

	@classmethod
	def parse(cls, text: str) -> Query:
		query = cls()
		query.text = text
		return query

	def first(self, name: str) -> str | None:
		values = self.parameters().get(name)
		if values:
			return values[0]
		else:
			return None

	def all(self, name: str) -> list[str]:
		return self.parameters().get(name, [])

	def parameters(self) -> dict[str, list[str]]:
		return parse_qs(self.text, keep_blank_values=True)

	def __contains__(self, name: str) -> bool:
		return name in self.parameters()

	def __str__(self) -> str:
		return self.text
