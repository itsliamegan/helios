from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING, TypeIs, cast, get_args, get_origin

from helios.declarative import Declaration, DeclarationError, split_nullable

from .codec import UUID
from .error import DatabaseError, ModelError

if TYPE_CHECKING:
	from .column import Column
	from .model import Model


@dataclass
class Target:
	model_type: type[Model]
	nullable: bool


class Relationship(ABC):
	name: str
	owner: type[Model]
	declaration: Declaration[object]

	def __init__(self, id_name: str):
		self.id_name = id_name
		self.checked = False

	def bind(self, declaration: Declaration[object]):
		self.name = declaration.name
		self.owner = cast("type[Model]", declaration.owner)
		self.declaration = declaration

	@property
	def label(self) -> str:
		return f"{self.owner.__name__}.{self.name}"

	@abstractmethod
	def settle(self, declaration: Declaration[object]) -> Target: ...

	@property
	def resolved(self) -> Target:
		target = self.declaration.resolve()
		assert isinstance(target, Target)
		return target

	@property
	def target(self) -> type[Model]:
		resolved = self.resolved
		if not self.checked:
			self.check(resolved)
			self.checked = True
		return resolved.model_type

	@abstractmethod
	def check(self, target: Target): ...

	@property
	@abstractmethod
	def owner_column(self) -> str: ...

	@property
	@abstractmethod
	def target_column(self) -> str: ...

	@abstractmethod
	def collect(self, parent: Model, matches: list[Model]) -> object: ...

	def __get__(self, instance: Model | None, owner: type) -> object:
		if instance is None:
			return self
		try:
			return instance._loaded[self.name]
		except KeyError:
			if instance._stored:
				message = (
					f"{self.label} is not loaded; "
					f"load it with store.preload(models, {self.name!r})"
				)
			else:
				message = (
					f"{self.label} is not loaded, "
					"and a model built with the constructor cannot be loaded"
				)
			raise ModelError(message) from None

	def __set__(self, instance: Model, value: object):
		raise AttributeError(f"{self.label} is read-only")


class BelongsTo(Relationship):
	def settle(self, declaration: Declaration[object]) -> Target:
		try:
			annotation, nullable = split_nullable(
				declaration.name,
				declaration.annotation,
			)
		except DeclarationError:
			annotation, nullable = None, False
		if not is_model(annotation):
			raise DeclarationError(
				declaration.name,
				f"expected a model, got {declaration.annotation!r}",
			)
		return Target(annotation, nullable)

	def check_id(self):
		column = self.owner._columns.get(self.id_name)
		if column is None:
			detail = "is not a column"
		elif not holds_uuid(column):
			detail = "does not hold a UUID"
		else:
			return
		raise ModelError(
			f"{self.label}: belongs_to names {self.id_name!r}, which {detail}"
		)

	def check(self, target: Target):
		column = self.owner.columns[self.id_name]
		if target.nullable != column.nullable:
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

	def collect(self, parent: Model, matches: list[Model]) -> object:
		id = parent._values[self.id_name]
		if id is None:
			return None
		if not matches:
			raise DatabaseError(
				f"{self.label} refers to {self.target.__name__} {id}, "
				"which does not exist"
			)
		return matches[0]

	def __set__(self, instance: Model, value: object):
		raise AttributeError(
			f"{self.label} is read-only; "
			f"use store.update on {self.owner.__name__}.{self.id_name}"
		)


class Inverse(Relationship):
	def check(self, target: Target):
		column = target.model_type.columns.get(self.id_name)
		if column is None or not holds_uuid(column):
			raise ModelError(
				f"{self.label}: {target.model_type.__name__}.{self.id_name} "
				"does not hold a UUID"
			)

	@property
	def owner_column(self) -> str:
		return "id"

	@property
	def target_column(self) -> str:
		return self.id_name


class HasMany(Inverse):
	def settle(self, declaration: Declaration[object]) -> Target:
		annotation = declaration.annotation
		members = get_args(annotation)
		if get_origin(annotation) is not list or len(members) != 1:
			members = (None,)
		if not is_model(members[0]):
			raise DeclarationError(
				declaration.name,
				f"expected list[<model>], got {annotation!r}",
			)
		return Target(members[0], nullable=False)

	def collect(self, parent: Model, matches: list[Model]) -> object:
		return list(matches)


class HasOne(Inverse):
	def settle(self, declaration: Declaration[object]) -> Target:
		try:
			annotation, nullable = split_nullable(
				declaration.name,
				declaration.annotation,
			)
		except DeclarationError:
			annotation, nullable = None, False
		if not nullable or not is_model(annotation):
			raise DeclarationError(
				declaration.name,
				f"expected <model> | None, got {declaration.annotation!r}",
			)
		return Target(annotation, nullable)

	def collect(self, parent: Model, matches: list[Model]) -> object:
		if len(matches) > 1:
			raise DatabaseError(
				f"{self.label} has several {self.target.__name__} rows "
				f"for {self.owner.__name__} {parent.id}"
			)
		return matches[0] if matches else None


def is_model(annotation: object) -> TypeIs[type[Model]]:
	from .model import Model

	return isinstance(annotation, type) and issubclass(annotation, Model)


def holds_uuid(column: Column) -> bool:
	return isinstance(column.codec, UUID)


def belongs_to(id_name: str, *, init: Literal[False] = False) -> Any:
	return BelongsTo(id_name)


def has_many(id_name: str, *, init: Literal[False] = False) -> Any:
	return HasMany(id_name)


def has_one(id_name: str, *, init: Literal[False] = False) -> Any:
	return HasOne(id_name)
