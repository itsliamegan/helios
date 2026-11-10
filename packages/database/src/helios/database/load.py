from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from .error import ModelError
from .model import Model
from .relationship import Relationship

if TYPE_CHECKING:
	from .store import Store


class Load:
	"""Loads relationship paths onto models of one type.

	Each path segment runs one query per batch of IDs, and paths that share a
	prefix query it once. A relationship with several targets runs those
	queries once for each target present. Every segment is queried again even
	when it is already loaded. Each row becomes one object, shared by every
	model that refers to it.
	"""

	def __init__(self, store: Store, model_type: type[Model], paths: Iterable[str]):
		self.store = store
		self.model_type = model_type
		self.branches: dict[str, Branch] = {}
		for path in paths:
			self.add(path)

	def add(self, path: str):
		subject = f"store.load on {self.model_type.__name__}"
		segments = path.split(".")
		if not all(segments):
			raise ModelError(
				f"{subject} has {path!r}, which is not a relationship path"
			)

		level = self.branches
		current = self.model_type
		for index, segment in enumerate(segments):
			continues = index < len(segments) - 1
			relationship = current.relationships.get(segment)
			if relationship is None:
				raise ModelError(
					f"{subject} has {path!r}, "
					f"where {current.__name__}.{segment} is not a relationship"
				)
			elif continues and len(relationship.target_types) > 1:
				raise ModelError(
					f"{subject} has {path!r}, "
					f"where {current.__name__}.{segment} has several targets"
				)

			for target_type in relationship.target_types:
				self.store.namespace(target_type)
			if continues:
				(current,) = relationship.target_types
			branch = level.setdefault(segment, Branch(relationship))
			level = branch.branches

	def load(self, models: Sequence[Model]):
		for branch in self.branches.values():
			branch.load(self.store, models)


class Branch:
	"""One relationship in a load, with the relationships loaded beneath it."""

	def __init__(self, relationship: Relationship):
		self.relationship = relationship
		self.branches: dict[str, Branch] = {}

	def load(self, store: Store, owners: Sequence[Model]):
		"""Load the relationship onto the owners, then each branch beneath it onto their targets."""

		relationship = self.relationship
		found = self.find_targets(store, owners)
		for owner in owners:
			value = owner._values[relationship.owner_column]
			owner._loaded[relationship.name] = relationship.target(
				owner,
				found.get(value, []),
			)

		targets: list[Model] = []
		for rows in found.values():
			targets.extend(rows)
		for branch in self.branches.values():
			branch.load(store, targets)

	def find_targets(
		self,
		store: Store,
		owners: Sequence[Model],
	) -> dict[UUID, list[Model]]:
		"""Find the owners' targets, grouped by owner column value.

		Each row is found once, however many owners match it. An owner with no
		targets has no entry.
		"""

		owner_column = self.relationship.owner_column
		target_column = self.relationship.target_column
		groups: dict[type[Model], list[Model]] = {}
		for owner in owners:
			target_type = self.relationship.target_type(owner)
			groups.setdefault(target_type, []).append(owner)

		batches: list[tuple[type[Model], list[UUID]]] = []
		size = store.connection.parameter_limit
		for target_type, group in groups.items():
			values = list(
				dict.fromkeys(
					owner._values[owner_column]
					for owner in group
					if owner._values[owner_column] is not None
				)
			)
			for start in range(0, len(values), size):
				batches.append((target_type, values[start : start + size]))

		found: dict[UUID, list[Model]] = {}
		for target_type, batch in batches:
			query = store.query(target_type).where({f"{target_column} in": batch})
			for row in query.all():
				found.setdefault(row._values[target_column], []).append(row)
		return found
