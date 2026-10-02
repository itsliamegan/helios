from abc import ABC, abstractmethod
from typing import Any, Literal, TYPE_CHECKING, TypeIs, cast, get_args, get_origin

from helios.declarative import Declaration, DeclarationError, split_nullable

from .codec import UUID
from .error import ModelError

if TYPE_CHECKING:
	from .columns import Columns
	from .model import Model


def belongs_to(id_name: str, *, init: Literal[False] = False) -> Any:
	return BelongsTo(id_name)


def has_many(id_name: str, *, init: Literal[False] = False) -> Any:
	return HasMany(id_name)


def has_one(id_name: str, *, init: Literal[False] = False) -> Any:
	return HasOne(id_name)


class Relationship(ABC):
	plural = False

	name: str
	owner: type[Model]
	declaration: Declaration
	_target: type[Model]
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
	def target(self) -> type[Model]:
		self.resolve()
		return self._target

	@property
	def nullable(self) -> bool:
		self.resolve()
		return self._nullable

	@abstractmethod
	def check(self): ...

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
		self._target = target
		self._nullable = nullable
		self.resolved = True

	def check_id(self, columns: Columns):
		column = columns.get(self.id_name)
		if column is None:
			detail = "is not a column"
		elif not isinstance(column.codec, UUID):
			detail = "does not hold a UUID"
		else:
			return
		raise ModelError(
			f"{self.label}: belongs_to names {self.id_name!r}, which {detail}"
		)

	def check(self):
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
	def check(self):
		column = self.target.columns.get(self.id_name)
		if column is None or not isinstance(column.codec, UUID):
			raise ModelError(
				f"{self.label}: {self.target.__name__}.{self.id_name} "
				"does not hold a UUID"
			)

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
		self._target = members[0]
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
		self._target = target
		self._nullable = nullable
		self.resolved = True


def is_model(annotation: object) -> TypeIs[type[Model]]:
	from .model import Model

	return isinstance(annotation, type) and issubclass(annotation, Model)
