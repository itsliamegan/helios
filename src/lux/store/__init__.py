import json
from datetime import datetime, UTC
from inspect import get_annotations as get_annots
from pathlib import Path
from typing import Any
from uuid import uuid4, UUID

from lux.app import Component, Context
from lux.http import Request, Response
from . import types

class Component(Component):
	def __init__(self, file: Path, schema: Schema):
		self.file = file
		self.schema = schema

	def before(self, req: Request, ctx: Context):
		ctx.store = load(self.file, self.schema)

	def after(self, res: Response, ctx: Context):
		save(self.file, ctx.store)

class ModelError(RuntimeError):
	pass

class Attribute:
	def __init__(
		self,
		name: str,
		typ: types.Type,
		default: Any | None = None,
		nullable: bool = False
	):
		self.name = name
		self.type = typ
		self.default = default
		self.nullable = nullable

	def __repr__(self) -> str:
		return f"Attribute({repr(self.name)}, {repr(self.type)}, default = {repr(self.default)}, nullable = {repr(self.nullable)})"

class Model:
	attrs = {}

	def __init_subclass__(cls):
		super().__init_subclass__()
		attrs = {}
		for attr in cls.attrs:
			attrs[attr.name] = attr
		cls.attrs = attrs

	def __init__(self, id: UUID, created_at: datetime, raw_attrs: dict[str, Any]):
		attrs = {}
		for name in raw_attrs:
			if name not in type(self).attrs:
				raise ModelError(f"extra attr '{name}'")
			attr = type(self).attrs[name]
			val = raw_attrs.get(name, None)
			if val is None:
				if attr.nullable:
					val = attr.default
				else:
					raise ModelError(f"missing attr '{name}'")
			attrs[name] = val
		for name in type(self).attrs:
			attr = type(self).attrs[name]
			if name not in attrs:
				if attr.default is not None or attr.nullable:
					attrs[name] = attr.default
				else:
					raise ModelError(f"missing attr '{name}'")
		self.id = id
		self.created_at = created_at
		self.attrs = attrs

	def __getattr__(self, name: str) -> Any:
		if name in self.attrs:
			return self.attrs[name]
		else:
			return super().__getattribute__(name)

	def __repr__(self) -> str:
		return f"{type(self).__name__}({repr(self.id)})"

class Schema:
	def __init__(self, raw_model_types: list[type[Model]]):
		model_types = {}
		for model_type in raw_model_types:
			model_types[model_type.__name__] = model_type
		self.model_types = model_types

	def get_model_type(self, name: str) -> type[Model]:
		return self.model_types[name]

class Store:
	def __init__(self, models: dict[UUID, Model] | None = None):
		if models is None:
			models = {}
		self.models = models

	def find_all(self, model_type: type[Model]) -> list[Model]:
		models = []
		for model in self.models.values():
			if type(model) == model_type:
				models.append(model)
		return models

	def find_one(self, model_type: type[Model], id: UUID) -> Model | None:
		return self.models.get(id, None)

	def find_by(self, model_type: type[Model], **attrs: dict[str, Any]) -> list[Model]:
		models = []
		for model in self.models.values():
			if type(model) == model_type:
				for attr in attrs:
					if getattr(model, attr) == attrs[attr]:
						models.append(model)
		return models

	def create(self, model_type: type[Model], **attrs: dict[str, Any]) -> Model:
		id = uuid4()
		created_at = datetime.now(UTC)
		model = model_type(id, created_at, attrs)
		self.models[id] = model
		return model

	def delete(self, model_type: type[Model], id: UUID):
		del self.models[id]

def load(path: Path, schema: Schema) -> Store:
	with open(path, "r") as file:
		data = json.load(file)
		store = decode(data, schema)
		return store

def save(path: Path, store: Store):
	with open(path, "w") as file:
		data = encode(store)
		json.dump(data, file)

def encode(store: Store) -> list[dict[str, Any]]:
	data = []
	for id, model in store.models.items():
		model_data = {}
		model_data["_type"] = type(model).__name__
		model_data["id"] = types.UUID().encode(model.id)
		model_data["created_at"] = types.Date().encode(model.created_at)
		for name in type(model).attrs:
			attr = type(model).attrs[name]
			raw_attr_val = getattr(model, attr.name)
			if raw_attr_val is None and attr.nullable:
				attr_val = None
			else:
				attr_val = attr.type.encode(raw_attr_val)
			model_data[attr.name] = attr_val
		data.append(model_data)
	return data

def decode(data: list[dict[str, Any]], schema: Schema) -> Store:
	models = {}
	for raw_model_data in data:
		model_type = schema.get_model_type(raw_model_data["_type"])
		id = types.UUID().decode(raw_model_data["id"])
		created_at = types.Date().decode(raw_model_data["created_at"])
		del raw_model_data["_type"]
		del raw_model_data["id"]
		del raw_model_data["created_at"]
		model_data = {}
		for name in raw_model_data:
			attr = model_type.attrs[name]
			raw_val = raw_model_data[name]
			if raw_val is None and attr.nullable:
				val = None
			else:
				val = attr.type.decode(raw_val)
			model_data[name] = val
		model = model_type(id, created_at, model_data)
		models[id] = model
	return Store(models)
