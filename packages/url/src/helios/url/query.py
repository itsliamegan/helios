from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Self
from urllib.parse import parse_qs, urlencode


@dataclass(init=False)
class Query:
	text: str
	parameters: dict[str, list[str]]

	def __init__(self, parameters: Mapping[str, str | Sequence[str]] | None = None):
		parameters = parameters or {}
		self.text = urlencode(parameters, doseq=True)
		self.parameters = parse_qs(self.text, keep_blank_values=True)

	@classmethod
	def parse(cls, text: str) -> Self:
		query = cls()
		query.text = text
		query.parameters = parse_qs(text, keep_blank_values=True)
		return query

	def first(self, name: str) -> str | None:
		values = self.parameters.get(name)
		if values:
			return values[0]
		else:
			return None

	def all(self, name: str) -> list[str]:
		return list(self.parameters.get(name, []))

	def __contains__(self, name: object) -> bool:
		return name in self.parameters

	def __str__(self) -> str:
		return self.text
