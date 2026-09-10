from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from helios.http.error import NotFoundError as BaseNotFoundError
from helios.persist.files import JSONValue

from .model import Model, ModelError


class NotFoundError(BaseNotFoundError):
	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")


class Schema:
	def __init__(self, raw_model_types: list[type[Model]]):
		model_types = {}
		for model_type in raw_model_types:
			model_types[model_type.__name__] = model_type
		self.model_types = model_types

	def get_model_type(self, name: str) -> type[Model]:
		return self.model_types[name]


class Pending:
	def __init__(self):
		self.saves: set[UUID] = set()
		self.deletes: set[UUID] = set()

	def clear(self):
		self.saves.clear()
		self.deletes.clear()

	def __bool__(self) -> bool:
		return bool(self.saves or self.deletes)


class Store:
	def __init__(self, models: dict[UUID, Model] | None = None):
		self.models = {}
		if models is not None:
			for id, model in models.items():
				self.models[id] = model
		self.pending = Pending()

	def find_all[T: Model](self, model_type: type[T]) -> list[T]:
		models: list[T] = []
		for model in self.models.values():
			if type(model) == model_type:
				models.append(cast(T, model))
		return models

	def find_one[T: Model](self, model_type: type[T], id: UUID) -> T:
		model = self.models.get(id, None)
		if type(model) is model_type:
			return cast(T, model)
		raise NotFoundError(model_type, id)

	def find_by[T: Model](self, model_type: type[T], **attrs: Any) -> list[T]:
		models: list[T] = []
		for model in self.models.values():
			if type(model) == model_type:
				matches = True
				for name, value in attrs.items():
					if getattr(model, name) != value:
						matches = False
				if matches:
					models.append(cast(T, model))
		return models

	def save(self, model: Model):
		current = self.models.get(model.id)
		if current is not None and current is not model:
			raise ModelError(f"{model!r} is not the live model held by this Store")

		if model.created_at is None:
			model.created_at = datetime.now(UTC)
		if model.id not in self.models:
			self.models[model.id] = model
		model._old_values.clear()
		self.pending.saves.add(model.id)
		self.pending.deletes.discard(model.id)

	def create[T: Model](self, model_type: type[T], **attrs: Any) -> T:
		model = model_type(**attrs)
		self.save(model)
		return model

	def delete(self, id: UUID):
		del self.models[id]
		self.pending.saves.discard(id)
		self.pending.deletes.add(id)


class Format:
	def __init__(self, schema: Schema):
		self.schema = schema

	def encode(self, store: Store) -> JSONValue:
		return cast(JSONValue, encode(store))

	def decode(self, value: JSONValue) -> Store:
		return decode(cast(list[dict[str, Any]], value), self.schema)


def encode(store: Store) -> list[dict[str, Any]]:
	data = []
	for model in store.models.values():
		model_data = {"_type": type(model).__name__}
		for name, attr in type(model).attrs.items():
			if name in model._old_values:
				raw_attr_val = model._old_values[name]
			else:
				raw_attr_val = getattr(model, name)
			if raw_attr_val is None and attr.nullable:
				attr_val = None
			else:
				attr_val = attr.type.encode(raw_attr_val)
			model_data[name] = attr_val
		data.append(model_data)
	return data


def decode(data: list[dict[str, Any]], schema: Schema) -> Store:
	models = {}
	for raw_model_data in data:
		model_type = schema.get_model_type(raw_model_data["_type"])
		model_data = {}
		for name, raw_val in raw_model_data.items():
			if name == "_type":
				continue
			attr = model_type.attrs[name]
			if raw_val is None:
				val = None
			else:
				val = attr.type.decode(raw_val)
			attr.check(val, model_type)
			model_data[name] = val
		for name, attr in model_type.attrs.items():
			if name in model_data:
				continue

			if not attr.required:
				val = attr.default
			elif attr.nullable:
				val = None
			else:
				raise ModelError(f"missing attr '{name}'")
			attr.check(val, model_type)
			model_data[name] = val
		model = model_type._hydrate(model_data)
		models[model.id] = model
	return Store(models)
