from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from .error import DatabaseError, ModelError
from .model import Model
from .relationship import Relationship

if TYPE_CHECKING:
	from .store import Store


class Branch:
	def __init__(self, relationship: Relationship):
		self.relationship = relationship
		self.branches: dict[str, Branch] = {}


class Preload:
	def __init__(self, store: Store, model_type: type[Model], paths: Iterable[str]):
		self.store = store
		self.model_type = model_type
		self.branches: dict[str, Branch] = {}
		for path in paths:
			self.add(path)

	def add(self, path: str):
		subject = f"store.preload on {self.model_type.__name__}"
		segments = path.split(".")
		if not all(segments):
			raise ModelError(
				f"{subject} has {path!r}, which is not a relationship path"
			)

		level = self.branches
		current = self.model_type
		for segment in segments:
			relationship = current.relationships.get(segment)
			if relationship is None:
				raise ModelError(
					f"{subject} has {path!r}, "
					f"where {current.__name__}.{segment} is not a relationship"
				)
			current = self.store.registry.get(relationship.target)
			branch = level.setdefault(segment, Branch(relationship))
			level = branch.branches

	def load(self, models: Sequence[Model]):
		self.load_branches(models, self.branches)

	def load_branches(self, models: Sequence[Model], branches: dict[str, Branch]):
		for name, branch in branches.items():
			pending = [model for model in models if name not in model._loaded]
			if pending:
				self.fill(branch.relationship, pending)

			children: dict[int, Model] = {}
			for model in models:
				loaded = model._loaded[name]
				for child in loaded if isinstance(loaded, list) else [loaded]:
					if isinstance(child, Model):
						children[id(child)] = child
			if branch.branches and children:
				self.load_branches(list(children.values()), branch.branches)

	def fill(self, relationship: Relationship, models: list[Model]):
		owner_column = relationship.owner_column
		target_column = relationship.target_column
		values = list(
			dict.fromkeys(
				model._values[owner_column]
				for model in models
				if model._values[owner_column] is not None
			)
		)

		matches: dict[object, list[Model]] = {}
		size = self.store.connection.parameter_limit
		for start in range(0, len(values), size):
			batch = values[start : start + size]
			query = self.store.query(relationship.target)
			for row in query.where({f"{target_column} in": batch}).all():
				matches.setdefault(row._values[target_column], []).append(row)

		for model in models:
			found = matches.get(model._values[owner_column], [])
			model._loaded[relationship.name] = self.loaded(relationship, model, found)

	def loaded(self, relationship: Relationship, model: Model, found: list[Model]):
		target = relationship.target.__name__
		owner = f"{relationship.owner.__name__} {model.id}"
		if relationship.plural:
			return found
		elif len(found) > 1:
			raise DatabaseError(
				f"{relationship.label} has several {target} rows for {owner}"
			)
		elif found:
			return found[0]
		elif relationship.nullable:
			return None
		else:
			raise DatabaseError(f"{relationship.label} has no {target} row for {owner}")
