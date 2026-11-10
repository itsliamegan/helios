from typing import Any, Literal, TYPE_CHECKING, Union, get_args, get_origin

from luna.declarative import DeclarationError

from ..error import DatabaseError, ModelError
from .inverse import Inverse
from .relationship import is_model

if TYPE_CHECKING:
	from ..columns import Columns
	from ..model import Model


# The `init` parameter tells type checkers that a relationship is not a
# constructor parameter.
def has_one_variant(
	id_name: str,
	*,
	variant_name: str,
	init: Literal[False] = False,
) -> Any:
	"""Declare the variant model that identifies this model in its `id_name` column.

	Annotate it as a union of two or more models. This model's `variant_name`
	column holds the table name of each row's variant. The column named by
	`id_name` must be unique.
	"""

	return HasOneVariant(id_name, variant_name)


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

		tables: set[str] = set()
		for variant in variants:
			if variant.table in tables:
				raise ModelError(
					f"{self.label}: {variant.__name__} shares its table "
					"with another variant"
				)
			tables.add(variant.table)
			self.check_target(variant)

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

	@property
	def owner_columns(self) -> tuple[str, ...]:
		return (self.owner_column, self.variant_name)

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
