from collections.abc import Iterator, Mapping

from .relationship import Relationship


class Relationships(Mapping[str, Relationship]):
	"""A model's relationships by name, each resolved when first read.

	Membership and iteration do not resolve relationships, so they work before
	a forward-referenced model is declared.
	"""

	def __init__(self, declared: Mapping[str, Relationship]):
		self.declared = declared

	def __getitem__(self, name: str) -> Relationship:
		relationship = self.declared[name]
		relationship.resolve()
		return relationship

	def __contains__(self, name: object) -> bool:
		return name in self.declared

	def __iter__(self) -> Iterator[str]:
		return iter(self.declared)

	def __len__(self) -> int:
		return len(self.declared)
