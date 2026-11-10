from typing import Any, Literal, get_args, get_origin

from luna.declarative import DeclarationError

from .inverse import Inverse
from .relationship import is_model


# The `init` parameter tells type checkers that a relationship is not a
# constructor parameter.
def has_many(id_name: str, *, init: Literal[False] = False) -> Any:
	"""Declare the models that identify this model in their `id_name` column.

	Annotate it as a list of the model type.
	"""

	return HasMany(id_name)


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
		self.check_target(members[0])

		self._target_types = (members[0],)
		self._nullable = False
		self.resolved = True
