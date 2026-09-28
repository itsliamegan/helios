from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(init=False)
class Input:
	items: dict[str, list[str]]

	def __init__(self, items: Mapping[str, str | list[str]] | None = None):
		self.items = {}
		for name, value in (items or {}).items():
			self.items[name] = list(value) if isinstance(value, list) else [value]

	def first(self, name: str) -> str | None:
		values = self.items.get(name)
		if values:
			return values[0]
		else:
			return None

	def all(self, name: str) -> list[str]:
		return list(self.items.get(name, []))

	def __delitem__(self, name: str):
		del self.items[name]

	def __contains__(self, name: str) -> bool:
		return name in self.items
