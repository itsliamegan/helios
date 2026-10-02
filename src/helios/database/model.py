from annotationlib import Format, get_annotations
from datetime import datetime
from typing import Any, ClassVar, dataclass_transform
from uuid import UUID, uuid4

from helios.declarative import (
	Declaration,
	check_init_keywords,
	check_single_base,
	declarations,
)

from .column import Column, Columns, declare, generated
from .error import ModelError
from .relationship import (
	BelongsTo,
	Relationship,
	Relationships,
	belongs_to,
	has_many,
	has_one,
)


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
		declare_columns(cls, dict(Model.columns.declared))

	def __init__(self, **columns: Any):
		self._values = type(self).initialize(columns)
		self._values["id"] = uuid4()
		self._loaded: dict[str, object] = {}
		self._stored = False

	@classmethod
	def hydrate(cls, values: dict[str, Any]) -> Model:
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

	def __repr__(self) -> str:
		return f"{type(self).__name__}({self.id!r})"


def declare_columns(model_type: type[Model], columns: dict[str, Column]):
	name = model_type.__name__
	own_columns = {}
	relationships = {}
	for declaration in declarations(model_type, settle, ModelError):
		default = declaration.default
		if isinstance(default, Relationship):
			default.bind(declaration)
			relationships[declaration.name] = default
		else:
			declared_column = default if isinstance(default, Column) else Column()
			declared_column.bind(declaration)
			own_columns[declaration.name] = declared_column

	for column_name, value in vars(model_type).items():
		if (
			isinstance(value, Column | Relationship)
			and column_name not in own_columns
			and column_name not in relationships
		):
			raise ModelError(f"'{name}.{column_name}' has no annotation")

	for column_name in [*vars(model_type), *own_columns]:
		if column_name in columns:
			raise ModelError(f"'{name}.{column_name}' is a reserved attribute")

	for column_name, declared_column in own_columns.items():
		setattr(model_type, column_name, declared_column)
		columns[column_name] = declared_column
	model_type.columns = Columns(columns)
	model_type.relationships = Relationships(relationships)

	for relationship in relationships.values():
		if isinstance(relationship, BelongsTo):
			relationship.check_id(model_type.columns)


def settle(declaration: Declaration[object]) -> object:
	if isinstance(declaration.default, Relationship):
		return declaration.default.settle(declaration)
	return declare(declaration)


METADATA = {"columns", "relationships"}

declare_columns(Model, {})
