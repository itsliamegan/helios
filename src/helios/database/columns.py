from collections.abc import Iterator, Mapping

from .column import Column


class Columns(Mapping[str, Column]):
	def __init__(self, declared: Mapping[str, Column]):
		self.declared = declared

	def __getitem__(self, name: str) -> Column:
		column = self.declared[name]
		column.resolve()
		return column

	def __contains__(self, name: object) -> bool:
		return name in self.declared

	def __iter__(self) -> Iterator[str]:
		return iter(self.declared)

	def __len__(self) -> int:
		return len(self.declared)
