from abc import ABC, abstractmethod
from typing import (
	Any,
	Literal,
	TYPE_CHECKING,
	TypeIs,
	Union,
	cast,
	get_args,
	get_origin,
)
import uuid

from luna.declarative import Declaration, DeclarationError, split_nullable

from .error import DatabaseError, ModelError

if TYPE_CHECKING:
	from .columns import Columns
	from .model import Model


# Each `init` parameter tells type checkers that a relationship is not a
# constructor parameter.


def belongs_to(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare the model that this model identifies in its `id_name` column.

	Annotate it with the model type, adding `| None` exactly when that column
	is nullable.
	"""

	return BelongsTo(id_name)


def has_many(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare the models that identify this model in their `id_name` column.

	Annotate it as a list of the model type.
	"""

	return HasMany(id_name)


def has_one(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare a model that identifies this model in its `id_name` column.

	Annotate it as `<model> | None`. The schema must keep the column unique. A
	second matching row is a `DatabaseError` when the relationship loads.
	"""

	return HasOne(id_name)


def has_one_variant(
	id_name: str,
	*,
	variant_name: str,
	init: Literal[False] = False,
) -> Any:
	"""Declare the variant model that identifies this model in its `id_name` column.

	Annotate it as a union of two or more models. This model's `variant_name`
	column holds the table name of each row's variant. The schema must keep
	`id_name` unique in each variant's table. Create a row and its variant in
	one transaction, so that no reader sees the row without its variant.
	"""

	return HasOneVariant(id_name, variant_name)


class Relationship(ABC):
	"""A model attribute that holds its target models once they are loaded.

	A loaded relationship is a snapshot; later writes do not change it. Updating
	a `belongs_to` ID unloads the associated relationship.
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
		"""Return the model that `model` loads this relationship from."""

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

	def check(self):
		"""Check the target models when the relationship is first read."""

		for target_type in self.target_types:
			column = target_type.columns.get(self.target_column)
			if column is None or column.annotation is not uuid.UUID:
				raise ModelError(
					f"{self.label}: {target_type.__name__}.{self.target_column} "
					"does not hold a UUID"
				)

	@property
	@abstractmethod
	def owner_column(self) -> str: ...

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


class BelongsTo(Relationship):
	def resolve(self):
		if self.resolved:
			return
		annotation = self.declaration.resolve()
		try:
			target, nullable = split_nullable(self.name, annotation)
		except DeclarationError:
			target, nullable = None, False
		if not is_model(target):
			raise self.declaration.reject(
				DeclarationError(self.name, f"expected a model, got {annotation!r}")
			)
		self._target_types = (target,)
		self._nullable = nullable
		self.resolved = True

	def check_columns(self, columns: Columns):
		column = columns.get(self.id_name)
		if column is None:
			detail = "is not a column"
		elif column.annotation is not uuid.UUID:
			detail = "does not hold a UUID"
		else:
			return
		raise ModelError(
			f"{self.label}: belongs_to names {self.id_name!r}, which {detail}"
		)

	def check(self):
		super().check()

		column = self.owner.columns[self.id_name]
		if self.nullable != column.nullable:
			raise ModelError(
				f"{self.label}: annotation must include None exactly when "
				f"{self.owner.__name__}.{self.id_name} is nullable"
			)

	@property
	def owner_column(self) -> str:
		return self.id_name

	@property
	def target_column(self) -> str:
		return "id"


class Inverse(Relationship):
	@property
	def owner_column(self) -> str:
		return "id"

	@property
	def target_column(self) -> str:
		return self.id_name


class HasMany(Inverse):
	plural = True

	def resolve(self):
		if self.resolved:
			return
		annotation = self.declaration.resolve()
		members = get_args(annotation)
		if get_origin(annotation) is not list or len(members) != 1:
			members = (None,)
		if not is_model(members[0]):
			raise self.declaration.reject(
				DeclarationError(
					self.name,
					f"expected list[<model>], got {annotation!r}",
				)
			)
		self._target_types = (members[0],)
		self._nullable = False
		self.resolved = True


class HasOne(Inverse):
	def resolve(self):
		if self.resolved:
			return
		annotation = self.declaration.resolve()
		try:
			target, nullable = split_nullable(self.name, annotation)
		except DeclarationError:
			target, nullable = None, False
		if not nullable or not is_model(target):
			raise self.declaration.reject(
				DeclarationError(
					self.name,
					f"expected <model> | None, got {annotation!r}",
				)
			)
		self._target_types = (target,)
		self._nullable = nullable
		self.resolved = True


class HasOneVariant(Inverse):
	"""A relationship to one of several models, named by the owner's variant column.

	Each variant is a model with a table of its own, and the variant column
	holds that table's name.
	"""

	def __init__(self, id_name: str, variant_name: str):
		super().__init__(id_name)
		self.variant_name = variant_name

	def resolve(self):
		if self.resolved:
			return
		annotation = self.declaration.resolve()
		members = get_args(annotation) if get_origin(annotation) is Union else ()
		variants = []
		for member in members:
			if is_model(member):
				variants.append(member)
		if len(members) < 2 or len(variants) != len(members):
			raise self.declaration.reject(
				DeclarationError(
					self.name,
					f"expected a union of models, got {annotation!r}",
				)
			)
		self._target_types = tuple(variants)
		self._nullable = False
		self.resolved = True

	def target_type(self, model: Model) -> type[Model]:
		table = model._values[self.variant_name]
		for target_type in self.target_types:
			if target_type.table == table:
				return target_type
		raise DatabaseError(
			f"{self.label} has unknown variant {table!r} "
			f"for {self.owner.__name__} {model.id}"
		)

	def check_columns(self, columns: Columns):
		column = columns.get(self.variant_name)
		if column is None:
			detail = "is not a column"
		elif column.annotation is not str:
			detail = "does not hold a str"
		else:
			return
		raise ModelError(
			f"{self.label}: has_one_variant names {self.variant_name!r}, which {detail}"
		)

	def check(self):
		tables: set[str] = set()
		for target_type in self.target_types:
			if target_type.table in tables:
				raise ModelError(
					f"{self.label}: {target_type.__name__} shares its table "
					"with another variant"
				)
			tables.add(target_type.table)

		super().check()


def is_model(annotation: object) -> TypeIs[type[Model]]:
	from .model import Model

	return isinstance(annotation, type) and issubclass(annotation, Model)
