from typing import Any, Literal, TYPE_CHECKING
import uuid

from luna.declarative import DeclarationError, split_nullable

from ..error import ModelError
from .relationship import Relationship, is_model

if TYPE_CHECKING:
	from ..columns import Columns


def belongs_to(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare the model that this model identifies in its `id_name` column.

	Annotate it with the model type, adding `| None` exactly when that column
	is nullable.
	"""

	return BelongsTo(id_name)


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
		elif nullable != self.owner.columns[self.id_name].nullable:
			raise ModelError(
				f"{self.label}: annotation must include None exactly when "
				f"{self.owner.__name__}.{self.id_name} is nullable"
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

	@property
	def owner_column(self) -> str:
		return self.id_name

	@property
	def target_column(self) -> str:
		return "id"
