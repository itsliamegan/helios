from collections.abc import Iterator, Mapping

from .relationship import Relationship


class Relationships(Mapping[str, Relationship]):
	def __init__(self, declared: dict[str, Relationship]):
		self.declared = declared
		self.checked: set[str] = set()

	def __getitem__(self, name: str) -> Relationship:
		relationship = self.declared[name]
		relationship.resolve()
		if name not in self.checked:
			relationship.check()
			self.checked.add(name)
		return relationship

	def __contains__(self, name: object) -> bool:
		return name in self.declared

	def __iter__(self) -> Iterator[str]:
		return iter(self.declared)

	def __len__(self) -> int:
		return len(self.declared)

	def of_kind[R: Relationship](self, kind: type[R]) -> list[R]:
		return [
			relationship
			for relationship in self.values()
			if isinstance(relationship, kind)
		]
