from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from .error import ModelError
from .model import Model
from .registry import Registry
from .relationship import Relationship

if TYPE_CHECKING:
	from .store import Store


class Branch:
	def __init__(self, relationship: Relationship):
		self.relationship = relationship
		self.branches: dict[str, Branch] = {}


def branches(
	registry: Registry,
	model_type: type[Model],
	paths: Iterable[str],
) -> dict[str, Branch]:
	subject = f"store.preload on {model_type.__name__}"
	tree: dict[str, Branch] = {}
	for path in paths:
		segments = path.split(".")
		if not all(segments):
			raise ModelError(
				f"{subject} has {path!r}, which is not a relationship path"
			)

		level = tree
		current = model_type
		for segment in segments:
			relationship = current.relationships.get(segment)
			if relationship is None:
				raise ModelError(
					f"{subject} has {path!r}, "
					f"where {current.__name__}.{segment} is not a relationship"
				)
			current = registry.get(relationship.target)
			branch = level.setdefault(segment, Branch(relationship))
			level = branch.branches
	return tree


def load(store: Store, models: Sequence[Model], branches: dict[str, Branch]):
	for name, branch in branches.items():
		relationship = branch.relationship
		pending = [model for model in models if name not in model._state.loaded]
		if pending:
			fill(store, relationship, pending)

		children: dict[int, Model] = {}
		for model in models:
			loaded = model._state.loaded[name]
			for child in loaded if isinstance(loaded, list) else [loaded]:
				if isinstance(child, Model):
					children[id(child)] = child
		if branch.branches and children:
			load(store, list(children.values()), branch.branches)


def fill(store: Store, relationship: Relationship, models: list[Model]):
	owner_column = relationship.owner_column
	target_column = relationship.target_column
	values = list(
		dict.fromkeys(
			model._state.values[owner_column]
			for model in models
			if model._state.values[owner_column] is not None
		)
	)

	matches: dict[object, list[Model]] = {}
	size = store.connection.parameter_limit
	for start in range(0, len(values), size):
		batch = values[start : start + size]
		query = store.query(relationship.target)
		for row in query.where({f"{target_column} in": batch}).all():
			matches.setdefault(row._state.values[target_column], []).append(row)

	for model in models:
		found = matches.get(model._state.values[owner_column], [])
		model._state.loaded[relationship.name] = relationship.collect(model, found)
