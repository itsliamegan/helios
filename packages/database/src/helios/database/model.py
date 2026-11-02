from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar, Self, dataclass_transform
from uuid import UUID, uuid4

from luna.declarative import (
	Namespace,
	check_init_keywords,
	check_reserved_names,
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
	"""A record in a database.

	A subclass indicates the table that its rows come from with the `table`
	attribute. A subclass declares each column as an annotated attribute and
	each relationship with `belongs_to`, `has_many`, or `has_one`. An annotation
	can name a type declared later, because each attribute resolves on first
	use.

	Attributes are read-only; writes must be performed through the `Store`. A
	model built by its constructor is never stored and has no `created_at`.

	Two models are equal only when they are the same object, so compare `id` to
	check for the same row.
	"""

	table: ClassVar[str] = ""
	columns: ClassVar[Columns] = Columns({})
	relationships: ClassVar[Relationships] = Relationships({})

	id: UUID = generated()
	created_at: datetime = generated()

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Model, ModelError)
		check_reserved_names(cls, Model, METADATA, ModelError)
		declare_attributes(cls)

	def __init__(self, **columns: Any):
		self._values = type(self).initialize(columns)
		self._values["id"] = uuid4()
		self._loaded: dict[str, Model | list[Model] | None] = {}
		self._stored = False

	@classmethod
	def hydrate(cls, values: Mapping[str, Any]) -> Self:
		"""Build a stored model from its decoded column values."""

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
	def initialize(cls, raw_columns: Mapping[str, Any]) -> dict[str, Any]:
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
		"""Set pending annotations to resolve by name in `namespace`.

		An annotation can name a type that its module imports only under
		`TYPE_CHECKING`. Setting the fallback namespace here allows the
		annotation to resolve to that type, if it is registered on the
		namespace.
		"""

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

	for name, column in columns.items():
		setattr(model_type, name, column)
	model_type.columns = Columns({**reserved, **columns})
	model_type.relationships = Relationships(relationships)

	for relationship in relationships.values():
		if isinstance(relationship, BelongsTo):
			relationship.check_id(model_type.columns)


METADATA = {"columns", "relationships"}

declare_attributes(Model)
