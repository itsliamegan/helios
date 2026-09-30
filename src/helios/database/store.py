from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .attribute import Attribute
from .codec import Scalar
from .condition import Clause, Group
from .error import DatabaseError, ModelError, NotFoundError
from .grammar import Grammar
from .model import Model
from .query import Query
from .sqlite import Connection
from .statement import Delete, Insert, Select, Statement, Update


class Registry:
	def __init__(self, model_types: Iterable[type[Model]]):
		self.model_types: set[type[Model]] = set()
		for model_type in model_types:
			if not isinstance(model_type, type) or not issubclass(model_type, Model):
				raise ModelError("registered model must be a Model subclass")
			if not isinstance(model_type.table, str) or not model_type.table:
				raise ModelError(
					f"{model_type.__name__} must declare a non-empty table"
				)
			self.model_types.add(model_type)

	def get[T: Model](self, model_type: type[T]) -> type[T]:
		if model_type not in self.model_types:
			raise ModelError(f"{model_type.__name__} is not a registered model")
		return model_type


class Store:
	def __init__(
		self,
		connection: Connection,
		model_types: Iterable[type[Model]] | Registry,
	):
		self.connection = connection
		self.registry = (
			model_types if isinstance(model_types, Registry) else Registry(model_types)
		)
		self.grammar = Grammar()

	def create[**P, T: Model](
		self,
		model_type: Callable[P, T],
		*args: P.args,
		**values: P.kwargs,
	) -> T:
		registered = self.registry.get(cast(type[T], model_type))
		record = model_type(*args, **values)
		created_at = datetime.now(UTC)
		attributes = {**record._values, "created_at": created_at}
		encoded = {
			name: attribute.encode(attributes[name], registered)
			for name, attribute in registered.attributes.items()
		}
		self.execute(Insert(registered.table, encoded))
		record._values["created_at"] = created_at
		return record

	def update(self, record: Model, **values: Any):
		model_type = self.registry.get(type(record))
		if not values:
			raise ModelError(f"{model_type.__name__}.update requires values")
		encoded: dict[str, Scalar | None] = {}
		for name, value in values.items():
			attribute = model_type.attribute(name)
			if not attribute.init:
				raise ModelError(f"{model_type.__name__}.{name} is generated")
			encoded[name] = attribute.encode(value, model_type)
		statement = Update(model_type.table, encoded, self.identifying(record))
		if self.execute(statement) == 0:
			raise NotFoundError(model_type, record.id)
		record._values.update(values)

	def delete(self, record: Model):
		model_type = self.registry.get(type(record))
		statement = Delete(model_type.table, self.identifying(record))
		if self.execute(statement) == 0:
			raise NotFoundError(model_type, record.id)

	def identifying(self, record: Model) -> tuple[Clause, ...]:
		return (Clause((Group.parse(type(record), {"id": record.id}),)),)

	def find_one[T: Model](self, model_type: type[T], id: UUID) -> T:
		found = self.query(model_type).where({"id": id}).first()
		if found is None:
			raise NotFoundError(model_type, id)
		return found

	def find_all[T: Model](self, model_type: type[T]) -> list[T]:
		return self.query(model_type).all()

	def find_by[T: Model](
		self,
		model_type: type[T],
		conditions: dict[str, Any],
	) -> list[T]:
		return self.query(model_type).where(conditions).all()

	def query[T: Model](self, model_type: type[T]) -> Query[T]:
		self.registry.get(model_type)
		return Query(self, model_type)

	def records[T: Model](self, model_type: type[T], statement: Select) -> list[T]:
		column_names, rows = self.run(statement)
		return [self.hydrate(model_type, column_names, row) for row in rows]

	def counts(self, attribute: Attribute, statement: Select) -> dict[Any, int]:
		_columns, rows = self.run(statement)
		try:
			return {attribute.decode(key): cast(int, count) for key, count in rows}
		except (TypeError, ValueError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

	def has_rows(self, statement: Select) -> bool:
		_columns, rows = self.run(statement)
		return len(rows) > 0

	def execute(self, statement: Statement) -> int:
		compiled = self.grammar.compile(statement)
		cursor = self.connection.execute(compiled.sql, compiled.parameters)
		try:
			return cursor.changed_rows
		finally:
			cursor.close()

	def run(
		self,
		statement: Statement,
	) -> tuple[tuple[str, ...], list[tuple[Scalar | None, ...]]]:
		compiled = self.grammar.compile(statement)
		return self.fetch(compiled.sql, compiled.parameters)

	def select[T: Model](
		self,
		model_type: type[T],
		sql: str,
		parameters: Iterable[Any],
	) -> list[T]:
		self.registry.get(model_type)
		column_names, rows = self.fetch(sql, parameters)
		return [self.hydrate(model_type, column_names, row) for row in rows]

	def fetch(
		self,
		sql: str,
		parameters: Iterable[Any],
	) -> tuple[tuple[str, ...], list[tuple[Scalar | None, ...]]]:
		cursor = self.connection.execute(sql, parameters)
		try:
			return cursor.columns, cursor.fetch_all()
		finally:
			cursor.close()

	def hydrate[T: Model](
		self,
		model_type: type[T],
		column_names: tuple[str, ...],
		row: tuple[Scalar | None, ...],
	) -> T:
		expected = tuple(model_type.attributes)
		if (
			len(column_names) != len(expected)
			or len(set(column_names)) != len(column_names)
			or set(column_names) != set(expected)
			or len(row) != len(column_names)
		):
			raise DatabaseError("database result does not match model columns")

		values: dict[str, Any] = {}
		try:
			for name, raw_value in zip(column_names, row, strict=True):
				values[name] = model_type.attributes[name].decode(raw_value)
		except (TypeError, ValueError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

		return cast(T, model_type.hydrate(values))
