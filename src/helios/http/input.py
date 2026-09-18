from dataclasses import dataclass


@dataclass(init=False)
class Input:
	items: dict[str, str | list[str]]

	def __init__(self, items: dict[str, str | list[str]] | None = None):
		self.items = items or {}

	def __getitem__(self, name: str) -> str | list[str]:
		return self.items[name]

	def __delitem__(self, name: str):
		del self.items[name]

	def __contains__(self, name: str) -> bool:
		return name in self.items
