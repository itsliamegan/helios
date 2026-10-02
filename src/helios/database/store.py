from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .clause import Clause, Group
from .codec import Scalar
from .column import Column
from .error import DatabaseError, ModelError, NotFoundError
from .grammar import Grammar
from .model import Model
from .query import Query
from .sqlite import Connection
from .statement import Delete, Insert, Raw, Select, Statement, Update


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
		model = model_type(*args, **values)
		model._values["created_at"] = datetime.now(UTC)
		encoded = {
			name: column.encode(model._values[name], registered)
			for name, column in registered.columns.items()
		}
		self.write(Insert(registered.table, encoded))
		return model

	def update(self, model: Model, **values: Any):
		model_type = self.registry.get(type(model))
		if not values:
			raise ModelError(f"{model_type.__name__}.update requires values")
		encoded: dict[str, Scalar | None] = {}
		for name, value in values.items():
			column = model_type.column(name)
			if not column.init:
				raise ModelError(f"{model_type.__name__}.{name} is generated")
			encoded[name] = column.encode(value, model_type)
		statement = Update(model_type.table, encoded, self.identifying(model))
		if self.write(statement) == 0:
			raise NotFoundError(model_type, model.id)
		model._values.update(values)

	def delete(self, model: Model):
		model_type = self.registry.get(type(model))
		statement = Delete(model_type.table, self.identifying(model))
		if self.write(statement) == 0:
			raise NotFoundError(model_type, model.id)

	def identifying(self, model: Model) -> tuple[Clause, ...]:
		return (Clause((Group.parse(type(model), {"id": model.id}),)),)

	def find_one[T: Model](self, model_type: type[T], id: UUID) -> T:
		found = self.query(model_type).where({"id": id}).first()
		if found is None:
			raise NotFoundError(model_type, id)
		return found

	def find_all[T: Model](self, model_type: type[T]) -> list[T]:
		return self.query(model_type).all()

	def find_by[T: Model](self, model_type: type[T], **columns: Any) -> list[T]:
		for name in columns:
			model_type.column(name)
		return self.query(model_type).where(columns).all()

	def query[T: Model](self, model_type: type[T]) -> Query[T]:
		self.registry.get(model_type)
		return Query(self, model_type)

	def select[T: Model](
		self,
		model_type: type[T],
		sql: str,
		parameters: Iterable[Any],
	) -> list[T]:
		self.registry.get(model_type)
		return self.models(model_type, Raw(sql, tuple(parameters)))

	def models[T: Model](self, model_type: type[T], statement: Statement) -> list[T]:
		column_names, rows = self.read(statement)
		return [self.hydrate(model_type, column_names, row) for row in rows]

	def counts(self, column: Column, statement: Select) -> dict[Any, int]:
		_columns, rows = self.read(statement)
		try:
			return {column.decode(key): cast(int, count) for key, count in rows}
		except (TypeError, ValueError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

	def has_rows(self, statement: Select) -> bool:
		_columns, rows = self.read(statement)
		return len(rows) > 0

	def read(
		self,
		statement: Statement,
	) -> tuple[tuple[str, ...], list[tuple[Scalar | None, ...]]]:
		compiled = self.grammar.compile(statement)
		cursor = self.connection.execute(compiled.sql, compiled.parameters)
		try:
			return cursor.columns, cursor.fetch_all()
		finally:
			cursor.close()

	def write(self, statement: Statement) -> int:
		compiled = self.grammar.compile(statement)
		cursor = self.connection.execute(compiled.sql, compiled.parameters)
		try:
			return cursor.changed_rows
		finally:
			cursor.close()

	def hydrate[T: Model](
		self,
		model_type: type[T],
		column_names: tuple[str, ...],
		row: tuple[Scalar | None, ...],
	) -> T:
		expected = tuple(model_type.columns)
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
				values[name] = model_type.columns[name].decode(raw_value)
		except (TypeError, ValueError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

		return cast(T, model_type.hydrate(values))
