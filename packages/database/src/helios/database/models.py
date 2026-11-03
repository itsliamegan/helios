from dataclasses import dataclass

from .error import ModelError, qualified
from .model import Model


@dataclass(init=False)
class Models:
	"""Models by their class name.

	A model not found in this collection defers to the parent namespace, if
	there is one. A pending annotation on any of this collection's models
	resolves through this collection.
	"""

	parent: Models | None
	named: dict[str, type[Model]]

	def __init__(self, parent: Models | None = None):
		self.parent = parent
		self.named = {}

	def model(self, model_type: type[Model]):
		if not isinstance(model_type, type) or not issubclass(model_type, Model):
			raise ModelError("registered model must be a Model subclass")
		if not isinstance(model_type.table, str) or not model_type.table:
			raise ModelError(f"{model_type.__name__} must declare a non-empty table")

		named = self.named.get(model_type.__name__)
		if named is not None:
			raise ModelError(
				f"registered models share the name {model_type.__name__}: "
				f"{qualified(named)}, {qualified(model_type)}"
			)

		self.named[model_type.__name__] = model_type
		for declaration in model_type.pending_declarations():
			declaration.fallback = self

	def find(self, name: str) -> type[Model] | None:
		found = self.named.get(name)
		if found is None and self.parent is not None:
			return self.parent.find(name)
		else:
			return found
