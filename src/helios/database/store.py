from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from .codec import Scalar
from .error import DatabaseError, ModelError, NotFoundError
from .model import Model
from .query import Filter, Membership, Query
from .sqlite import Connection, quote_identifier


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
		names = tuple(registered.attributes)
		columns = ", ".join(quote_identifier(name) for name in names)
		placeholders = ", ".join("?" for _ in names)
		parameters = [
			registered.attributes[name].encode(attributes[name], registered)
			for name in names
		]
		sql = (
			f"INSERT INTO {quote_identifier(registered.table)} ({columns}) "
			f"VALUES ({placeholders})"
		)
		self.connection.execute(sql, parameters).close()
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
		assignments = ", ".join(f"{quote_identifier(name)} = ?" for name in encoded)
		parameters = [
			*encoded.values(),
			model_type.attributes["id"].encode(record.id, model_type),
		]
		sql = (
			f"UPDATE {quote_identifier(model_type.table)} SET {assignments} "
			f"WHERE {quote_identifier("id")} = ?"
		)
		cursor = self.connection.execute(sql, parameters)
		try:
			changed_rows = cursor.changed_rows
		finally:
			cursor.close()
		if changed_rows == 0:
			raise NotFoundError(model_type, record.id)
		record._values.update(values)

	def delete(self, record: Model):
		model_type = self.registry.get(type(record))
		sql = (
			f"DELETE FROM {quote_identifier(model_type.table)} "
			f"WHERE {quote_identifier("id")} = ?"
		)
		identifier = model_type.attributes["id"].encode(record.id, model_type)
		cursor = self.connection.execute(sql, (identifier,))
		try:
			changed_rows = cursor.changed_rows
		finally:
			cursor.close()
		if changed_rows == 0:
			raise NotFoundError(model_type, record.id)

	def find_one[T: Model](self, model_type: type[T], id: UUID) -> T:
		found = self.query(model_type).where(id=id).first()
		if found is None:
			raise NotFoundError(model_type, id)
		return found

	def find_all[T: Model](self, model_type: type[T]) -> list[T]:
		return self.query(model_type).all()

	def find_by[T: Model](self, model_type: type[T], **attributes: Any) -> list[T]:
		return self.query(model_type).where(**attributes).all()

	def query[T: Model](self, model_type: type[T]) -> Query[T]:
		self.registry.get(model_type)
		return Query(self, model_type)

	def execute[T: Model](self, query: Query[T]) -> list[T]:
		model_type = query.model_type
		columns = ", ".join(quote_identifier(name) for name in model_type.attributes)
		clauses: list[str] = []
		parameters: list[Any] = []
		for predicate in query.predicates:
			match predicate:
				case Filter(name=name, value=None):
					clauses.append(f"{quote_identifier(name)} IS NULL")
				case Filter(name=name, value=value):
					clauses.append(f"{quote_identifier(name)} = ?")
					parameters.append(value)
				case Membership(name=name, values=values, includes_null=includes_null):
					placeholders = ", ".join("?" for _ in values)
					clause = f"{quote_identifier(name)} IN ({placeholders})"
					if includes_null:
						clause = f"({clause} OR {quote_identifier(name)} IS NULL)"
					clauses.append(clause)
					parameters.extend(values)
		where = f" WHERE {" AND ".join(clauses)}" if clauses else ""
		order = ""
		if query.ordering is not None:
			name, direction = query.ordering
			order = f" ORDER BY {quote_identifier(name)} {direction.upper()}"
		limit = ""
		if query.count is not None:
			limit = " LIMIT ?"
			parameters.append(query.count)
		sql = (
			f"SELECT {columns} FROM {quote_identifier(model_type.table)}"
			f"{where}{order}{limit}"
		)
		return self.execute_select(model_type, sql, parameters)

	def select[T: Model](
		self,
		model_type: type[T],
		sql: str,
		parameters: Iterable[Any],
	) -> list[T]:
		self.registry.get(model_type)
		return self.execute_select(model_type, sql, parameters)

	def execute_select[T: Model](
		self,
		model_type: type[T],
		sql: str,
		parameters: Iterable[Any],
	) -> list[T]:
		cursor = self.connection.execute(sql, parameters)
		try:
			column_names = cursor.columns
			rows = cursor.fetch_all()
		finally:
			cursor.close()
		return [self.hydrate(model_type, column_names, row) for row in rows]

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
				values[name] = model_type.attributes[name].decode(raw_value, model_type)
		except (TypeError, ValueError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

		return cast(T, model_type.hydrate(values))
