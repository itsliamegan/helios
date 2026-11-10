from typing import Any, Literal

from luna.declarative import DeclarationError, split_nullable

from .inverse import Inverse
from .relationship import is_model


def has_one(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare a model that identifies this model in its `id_name` column.

	Annotate it as `<model> | None`. The schema must keep the column unique. A
	second matching row is a `DatabaseError` when the relationship loads.
	"""

	return HasOne(id_name)


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
		self.check_target(target)

		self._target_types = (target,)
		self._nullable = nullable
		self.resolved = True
