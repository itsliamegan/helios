from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass
class File:
	content: bytes
	filename: str
	content_type: str


@dataclass(init=False)
class Files:
	items: dict[str, list[File]]

	def __init__(self, items: Mapping[str, File | Sequence[File]] | None = None):
		self.items = {}
		for name, value in (items or {}).items():
			self.items[name] = [value] if isinstance(value, File) else list(value)

	def first(self, name: str) -> File | None:
		files = self.items.get(name)
		if files:
			return files[0]
		else:
			return None

	def all(self, name: str) -> list[File]:
		return list(self.items.get(name, []))

	def __contains__(self, name: str) -> bool:
		return name in self.items
