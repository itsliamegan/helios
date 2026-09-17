from dataclasses import dataclass


@dataclass
class File:
	content: bytes
	filename: str
	content_type: str


@dataclass(init=False)
class Files:
	items: dict[str, File | list[File]]

	def __init__(self, items: dict[str, File | list[File]] | None = None):
		self.items = items or {}

	def __getitem__(self, name: str) -> File | list[File]:
		return self.items[name]

	def __contains__(self, name: str) -> bool:
		return name in self.items
