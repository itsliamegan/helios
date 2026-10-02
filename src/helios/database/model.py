from annotationlib import Format, get_annotations
from datetime import datetime
from typing import Any, ClassVar, Self, dataclass_transform
from uuid import UUID, uuid4

from helios.declarative import (
	Namespace,
	check_init_keywords,
	check_single_base,
	declarations,
)

from .column import Column, generated
from .columns import Columns
from .error import ModelError
from .relationship import (
	BelongsTo,
	Relationship,
	belongs_to,
	has_many,
	has_one,
)
from .relationships import Relationships


@dataclass_transform(
	kw_only_default=True,
	eq_default=False,
	field_specifiers=(generated, belongs_to, has_many, has_one),
)
class Model:
	table: ClassVar[str] = ""
	columns: ClassVar[Columns] = Columns({})
	relationships: ClassVar[Relationships] = Relationships({})

	id: UUID = generated()
	created_at: datetime = generated()

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Model, ModelError)
		annotations = get_annotations(cls, format=Format.FORWARDREF)
		for name in METADATA:
			if name in vars(cls) or name in annotations:
				raise ModelError(f"{cls.__name__}.{name} is model metadata")
		declare_attributes(cls)

	def __init__(self, **columns: Any):
		self._values = type(self).initialize(columns)
		self._values["id"] = uuid4()
		self._loaded: dict[str, Model | list[Model] | None] = {}
		self._stored = False

	@classmethod
	def hydrate(cls, values: dict[str, Any]) -> Self:
		model = cls.__new__(cls)
		model._values = {name: values[name] for name in cls.columns}
		model._loaded = {}
		model._stored = True
		return model

	@classmethod
	def column(cls, name: str) -> Column:
		if name in cls.relationships:
			raise ModelError(f"{cls.__name__}.{name} is a relationship, not a column")
		try:
			return cls.columns[name]
		except KeyError:
			raise ModelError(f"{cls.__name__} has no column {name!r}") from None

	@classmethod
	def initialize(cls, raw_columns: dict[str, Any]) -> dict[str, Any]:
		initialized = {
			name: definition
			for name, definition in cls.columns.items()
			if definition.init
		}
		check_init_keywords(
			cls,
			"attributes",
			raw_columns,
			initialized,
			[name for name, definition in initialized.items() if definition.required],
		)

		values = {}
		for name, definition in initialized.items():
			value = raw_columns.get(name, definition.default)
			try:
				definition.check(value)
			except (TypeError, ValueError) as error:
				raise ModelError(f"{cls.__name__}.{name}: {error}") from error
			values[name] = value
		return values

	@classmethod
	def fall_back_to(cls, namespace: Namespace):
		attributes = [
			*cls.columns.declared.values(),
			*cls.relationships.declared.values(),
		]
		for attribute in attributes:
			if attribute.declaration.pending:
				attribute.declaration.fallback = namespace

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"


def declare_attributes(model_type: type[Model]):
	reserved = Model.columns.declared
	columns = {}
	relationships = {}
	for declaration in declarations(model_type, ModelError):
		default = declaration.default
		if isinstance(default, Relationship):
			relationship = default
			relationship.bind(declaration)
			relationships[declaration.name] = relationship
		else:
			column = default if isinstance(default, Column) else Column()
			column.bind(declaration)
			columns[declaration.name] = column

	for attribute in [*columns.values(), *relationships.values()]:
		if not attribute.declaration.pending:
			attribute.resolve()

	for name, value in vars(model_type).items():
		if (
			isinstance(value, Column | Relationship)
			and name not in columns
			and name not in relationships
		):
			raise ModelError(f"'{model_type.__name__}.{name}' has no annotation")

	for name in [*vars(model_type), *columns]:
		if name in reserved:
			raise ModelError(f"'{model_type.__name__}.{name}' is a reserved attribute")

	for name, column in columns.items():
		setattr(model_type, name, column)
	model_type.columns = Columns({**reserved, **columns})
	model_type.relationships = Relationships(relationships)

	for relationship in relationships.values():
		if isinstance(relationship, BelongsTo):
			relationship.check_id(model_type.columns)


METADATA = {"columns", "relationships"}

declare_attributes(Model)
