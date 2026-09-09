from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, ClassVar, Literal, cast, overload
from uuid import UUID, uuid4

from helios.app import Component, Context
from helios.http import Request, Response
from helios.http.error import NotFoundError as BaseNotFoundError

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


class NotFoundError(BaseNotFoundError):
	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")


_MISSING: Any = object()


class Attribute[StoredT, ValueT = StoredT]:
	def __init__(
		self,
		typ: types.Type[StoredT],
		*,
		default: ValueT,
		nullable: bool,
		init: bool,
	):
		self.name: str | None = None
		self.owner: type[Model] | None = None
		self.type = typ
		self.default = None if default is _MISSING else default
		self.required = default is _MISSING
		self.nullable = nullable
		self.init = init

	def __set_name__(self, owner: type[Model], name: str):
		self.owner = owner
		self.name = name

	@overload
	def __get__(
		self, instance: None, owner: type[Model]
	) -> Attribute[StoredT, ValueT]: ...

	@overload
	def __get__(self, instance: Model, owner: type[Model]) -> ValueT: ...

	def __get__(
		self, instance: Model | None, owner: type[Model]
	) -> Attribute[StoredT, ValueT] | ValueT:
		if instance is None:
			return self
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		try:
			return instance._values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def __set__(self, instance: Model, value: ValueT) -> None:
		if self.name is None:
			raise AttributeError("attribute has not been assigned to a model")
		instance._values[self.name] = value

	def __repr__(self) -> str:
		return f"Attribute({self.name!r}, {self.type!r}, default={self.default!r}, nullable={self.nullable!r})"


@overload
def attr[T](
	typ: type[T],
	*,
	default: T = _MISSING,
	nullable: Literal[False] = False,
	init: bool = True,
) -> Attribute[T]: ...


@overload
def attr[T](
	typ: type[T],
	*,
	default: T | None = _MISSING,
	nullable: Literal[True],
	init: bool = True,
) -> Attribute[T, T | None]: ...


def attr(
	typ: type[Any],
	*,
	default: Any = _MISSING,
	nullable: bool = False,
	init: bool = True,
) -> Attribute[Any, Any]:
	return Attribute(
		types.Type.resolve(typ),
		default=default,
		nullable=nullable,
		init=init,
	)


class _ModelMeta(type):
	attrs: dict[str, Attribute[Any, Any]]

	def __new__(
		metaclass,
		name: str,
		bases: tuple[type, ...],
		namespace: dict[str, Any],
	):
		if bases and "attrs" in namespace:
			raise ModelError(
				f"{name}.attrs is model metadata; declare named attributes instead"
			)

		model_bases = [base for base in bases if isinstance(base, _ModelMeta)]
		if len(model_bases) > 1:
			raise ModelError(f"{name} cannot inherit from multiple model classes")

		attrs = dict(model_bases[0].attrs) if model_bases else {}

		for attr_name, value in namespace.items():
			if attr_name in attrs:
				if not attrs[attr_name].init:
					raise ModelError(f"'{name}.{attr_name}' is a reserved attr")
				if not isinstance(value, Attribute):
					raise ModelError(
						f"'{name}.{attr_name}' replaces an inherited attr with a non-Attribute"
					)
			if isinstance(value, Attribute):
				attrs[attr_name] = value

		model_type = super().__new__(metaclass, name, bases, namespace)
		model_type.attrs = attrs
		return model_type


class Model(metaclass=_ModelMeta):
	attrs: ClassVar[dict[str, Attribute[Any, Any]]]

	id = attr(UUID, init=False)
	created_at = cast(Attribute[datetime, datetime | None], attr(datetime, init=False))

	def __init__(self, **attrs: Any):
		self._values = type(self)._initialize(attrs)
		self.id = uuid4()
		self.created_at = None

	@classmethod
	def _hydrate(cls, values: dict[str, Any]) -> Model:
		model = cls.__new__(cls)
		model._values = dict(values)
		return model

	@classmethod
	def _initialize(cls, raw_attrs: dict[str, Any]) -> dict[str, Any]:
		values = {}
		for name, val in raw_attrs.items():
			attr = cls.attrs.get(name)
			if attr is None or not attr.init:
				raise ModelError(f"extra attr '{name}'")
			if val is None:
				if attr.nullable:
					val = attr.default
				else:
					raise ModelError(f"missing attr '{name}'")
			values[name] = val

		for name, attr in cls.attrs.items():
			if not attr.init:
				continue
			if name not in values:
				if not attr.required or attr.nullable:
					values[name] = attr.default
				else:
					raise ModelError(f"missing attr '{name}'")
		return values

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"


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

	def add(self, model: Model) -> None:
		if model.created_at is None:
			model.created_at = datetime.now(UTC)
		self.models[model.id] = model

	def create[T: Model](self, model_type: type[T], **attrs: Any) -> T:
		model = model_type(**attrs)
		self.add(model)
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
	for model in store.models.values():
		model_data = {"_type": type(model).__name__}
		for name, attr in type(model).attrs.items():
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
			if raw_val is None and attr.nullable:
				val = attr.default
			else:
				val = attr.type.decode(raw_val)
			model_data[name] = val
		for name, attr in model_type.attrs.items():
			if name not in model_data:
				if not attr.required or attr.nullable:
					model_data[name] = attr.default
				else:
					raise ModelError(f"missing attr '{name}'")
		model = model_type._hydrate(model_data)
		models[model.id] = model
	return Store(models)
