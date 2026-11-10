from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeIs, cast

from luna.declarative import Declaration

from ..error import DatabaseError, ModelError

if TYPE_CHECKING:
	from ..columns import Columns
	from ..model import Model


class Relationship(ABC):
	"""A model attribute that holds its target models once they are loaded.

	A loaded relationship is a snapshot; later writes do not change it. Updating
	one of its `owner_columns` unloads it.
	"""

	plural = False

	name: str
	owner: type[Model]
	declaration: Declaration
	_target_types: tuple[type[Model], ...]
	_nullable: bool

	def __init__(self, id_name: str):
		self.id_name = id_name
		self.resolved = False

	def bind(self, declaration: Declaration):
		self.name = declaration.name
		self.owner = cast("type[Model]", declaration.owner)
		self.declaration = declaration

	@property
	def label(self) -> str:
		return f"{self.owner.__name__}.{self.name}"

	@abstractmethod
	def resolve(self): ...

	@property
	def target_types(self) -> tuple[type[Model], ...]:
		self.resolve()
		return self._target_types

	@property
	def nullable(self) -> bool:
		self.resolve()
		return self._nullable

	def target_type(self, model: Model) -> type[Model]:
		"""Return the model type that `model` loads this relationship from."""

		(target_type,) = self.target_types
		return target_type

	def target(self, model: Model, found: list[Model]) -> Model | list[Model] | None:
		"""Return the loaded target of `model` from the rows found for it."""

		owner = f"{self.owner.__name__} {model.id}"
		if self.plural:
			return found
		elif len(found) > 1:
			raise DatabaseError(
				f"{self.label} has several {self.target_type(model).__name__} rows "
				f"for {owner}"
			)
		elif found:
			return found[0]
		elif self.nullable:
			return None
		else:
			raise DatabaseError(
				f"{self.label} has no {self.target_type(model).__name__} row "
				f"for {owner}"
			)

	def check_columns(self, columns: Columns):
		"""Check the owner's columns when the owner is declared."""

	@property
	@abstractmethod
	def owner_column(self) -> str: ...

	@property
	def owner_columns(self) -> tuple[str, ...]:
		"""The owner's columns that decide which rows this relationship loads."""

		return (self.owner_column,)

	@property
	@abstractmethod
	def target_column(self) -> str: ...

	def __get__(self, instance: Model | None, owner: type) -> object:
		if instance is None:
			return self
		try:
			return instance._loaded[self.name]
		except KeyError:
			# Not an `AttributeError`, which templates would report as a missing
			# attribute rather than an unloaded relationship.
			raise ModelError(f"{self.label} is not loaded") from None

	def __set__(self, instance: Model, value: object):
		raise AttributeError(f"{self.label} is read-only")


def is_model(annotation: object) -> TypeIs[type[Model]]:
	from ..model import Model

	return isinstance(annotation, type) and issubclass(annotation, Model)
