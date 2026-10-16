from collections.abc import Iterable

from .error import ModelError
from .model import Model


class Registry:
	def __init__(self, model_types: Iterable[type[Model]]):
		self.model_types: set[type[Model]] = set()
		self.names: dict[str, type[Model]] = {}
		for model_type in model_types:
			if not isinstance(model_type, type) or not issubclass(model_type, Model):
				raise ModelError("registered model must be a Model subclass")
			if not isinstance(model_type.table, str) or not model_type.table:
				raise ModelError(
					f"{model_type.__name__} must declare a non-empty table"
				)
			named = self.names.setdefault(model_type.__name__, model_type)
			if named is not model_type:
				raise ModelError(
					f"registered models share the name {model_type.__name__}: "
					f"{qualified(named)}, {qualified(model_type)}"
				)
			self.model_types.add(model_type)

		for model_type in self.model_types:
			model_type.fall_back_to(self)

	def get[T: Model](self, model_type: type[T]) -> type[T]:
		if model_type not in self.model_types:
			raise ModelError(f"{model_type.__name__} is not a registered model")
		return model_type

	def find(self, name: str) -> type[Model] | None:
		return self.names.get(name)


def qualified(model_type: type[Model]) -> str:
	return f"{model_type.__module__}.{model_type.__qualname__}"
