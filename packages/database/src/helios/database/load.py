from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

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

	def load(self, store: Store, models: Sequence[Model]):
		"""Load the relationship onto the models, then the branches beneath it."""

		relationship = self.relationship
		groups: dict[type[Model], list[Model]] = {}
		for model in models:
			groups.setdefault(relationship.target_type(model), []).append(model)

		for target_type, group in groups.items():
			rows = self.rows(store, target_type, group)
			for model in group:
				found = rows.get(model._values[relationship.owner_column], [])
				model._loaded[relationship.name] = relationship.target(model, found)

		if self.branches:
			targets = self.targets(models)
			for branch in self.branches.values():
				branch.load(store, targets)

	def rows(
		self,
		store: Store,
		target_type: type[Model],
		models: Sequence[Model],
	) -> dict[object, list[Model]]:
		"""Return the target rows for the models, by their target column value."""

		owner_column = self.relationship.owner_column
		target_column = self.relationship.target_column
		values = list(
			dict.fromkeys(
				model._values[owner_column]
				for model in models
				if model._values[owner_column] is not None
			)
		)

		rows: dict[object, list[Model]] = {}
		size = store.connection.parameter_limit
		for start in range(0, len(values), size):
			batch = values[start : start + size]
			query = store.query(target_type)
			for row in query.where({f"{target_column} in": batch}).all():
				rows.setdefault(row._values[target_column], []).append(row)
		return rows

	def targets(self, models: Sequence[Model]) -> list[Model]:
		"""Return the models' loaded targets, each once."""

		targets: dict[int, Model] = {}
		for model in models:
			loaded = model._loaded[self.relationship.name]
			if isinstance(loaded, list):
				for target in loaded:
					targets[id(target)] = target
			elif loaded is not None:
				targets[id(loaded)] = loaded
		return list(targets.values())
