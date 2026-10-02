from collections.abc import Iterable

from helios.declarative import Declaration

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

		pending = {
			model_type: pending_declarations(model_type)
			for model_type in self.model_types
		}
		for model_type, declarations in pending.items():
			for declaration in declarations:
				self.check_agreement(model_type, declaration)
		for declarations in pending.values():
			for declaration in declarations:
				declaration.fallback = self

	def get[T: Model](self, model_type: type[T]) -> type[T]:
		if model_type not in self.model_types:
			raise ModelError(f"{model_type.__name__} is not a registered model")
		return model_type

	def find(self, name: str) -> type[Model] | None:
		return self.names.get(name)

	def check_agreement(self, model_type: type[Model], declaration: Declaration):
		previous = declaration.fallback
		if not isinstance(previous, Registry):
			return
		for name in self.names.keys() & previous.names.keys():
			if self.names[name] is not previous.names[name]:
				raise ModelError(
					f"{model_type.__name__} is already registered with "
					f"{qualified(previous.names[name])} as {name}, "
					f"not {qualified(self.names[name])}"
				)


def pending_declarations(model_type: type[Model]) -> list[Declaration]:
	attributes = [
		*model_type.columns.declared.values(),
		*model_type.relationships.declared.values(),
	]
	return [
		attribute.declaration
		for attribute in attributes
		if attribute.declaration.owner is model_type and attribute.declaration.pending
	]


def qualified(model_type: type[Model]) -> str:
	return f"{model_type.__module__}.{model_type.__qualname__}"
