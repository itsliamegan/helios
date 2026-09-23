from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from helios.http.error import NotFoundError as BaseNotFoundError

from . import types
from .model import Attribute, Model, ModelError, Status
from .query import Filter, Membership, Predicate, Query
from .sqlite import Connection, DatabaseError, quote_identifier


class NotFoundError(BaseNotFoundError):
	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")


class Registry:
	def __init__(self, model_types: Iterable[type[Model]]):
		self.model_types: set[type[Model]] = set()
		for model_type in model_types:
			if not isinstance(model_type, type) or not issubclass(model_type, Model):
				raise ModelError("registered model must be a Model subclass")
			table = model_type.__dict__.get("table")
			if not isinstance(table, str) or not table:
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
		self.identity: dict[tuple[type[Model], UUID], Model] = {}

	def create[T: Model](self, model_type: type[T], **attrs: Any) -> T:
		self.registry.get(model_type)
		model = model_type(**attrs)
		self.save(model)
		return model

	def save(self, model: Model):
		model_type = self.registry.get(type(model))
		if model._status is Status.NEW:
			self.insert(model_type, model)
			return
		self.update(model_type, model)

	def insert[T: Model](self, model_type: type[T], model: T):
		created_at = datetime.now(UTC)
		values = dict(model.values)
		values["created_at"] = created_at
		changes = model._changes.snapshot()
		names = tuple(model_type.attrs)
		columns = ", ".join(quote_identifier(name) for name in names)
		placeholders = ", ".join("?" for _ in names)
		parameters = [self.encode(model_type, name, values[name]) for name in names]
		sql = (
			f"INSERT INTO {quote_identifier(model_type.table)} ({columns}) "
			f"VALUES ({placeholders})"
		)
		self.connection.execute(sql, parameters).close()

		model.values["created_at"] = created_at
		model._status = Status.PERSISTED
		model._changes.accept(changes)
		self.identity[(model_type, model.id)] = model

	def update[T: Model](self, model_type: type[T], model: T):
		changes = model._changes.snapshot()
		names = tuple(name for name in model_type.attrs if name in changes)
		if not names:
			return
		values = {name: model.values[name] for name in names}
		assignments = ", ".join(f"{quote_identifier(name)} = ?" for name in names)
		parameters = [self.encode(model_type, name, values[name]) for name in names]
		parameters.append(types.encode(model_type.attrs["id"].type, model.id))
		sql = (
			f"UPDATE {quote_identifier(model_type.table)} SET {assignments} "
			f"WHERE {quote_identifier("id")} = ?"
		)
		self.connection.execute(sql, parameters).close()
		model._changes.accept(changes)

	def delete(self, model: Model):
		model_type = self.registry.get(type(model))
		identifier = types.encode(model_type.attrs["id"].type, model.id)
		sql = (
			f"DELETE FROM {quote_identifier(model_type.table)} "
			f"WHERE {quote_identifier("id")} = ?"
		)
		self.connection.execute(sql, (identifier,)).close()
		model._status = Status.DELETED
		key = (model_type, model.id)
		if self.identity.get(key) is model:
			del self.identity[key]

	def find_one[T: Model](self, model_type: type[T], id: UUID) -> T:
		found = self.query(model_type).where(id=id).first()
		if found is None:
			raise NotFoundError(model_type, id)
		return found

	def find_all[T: Model](self, model_type: type[T]) -> list[T]:
		return self.query(model_type).all()

	def find_by[T: Model](self, model_type: type[T], **attrs: Any) -> list[T]:
		return self.query(model_type).where(**attrs).all()

	def query[T: Model](self, model_type: type[T]) -> Query[T]:
		self.registry.get(model_type)
		return Query(self, model_type)

	def execute_query[T: Model](
		self,
		model_type: type[T],
		predicates: tuple[Predicate, ...],
		ordering: tuple[str, str] | None,
		count: int | None,
	) -> list[T]:
		columns = ", ".join(quote_identifier(name) for name in model_type.attrs)
		clauses: list[str] = []
		parameters: list[Any] = []
		for predicate in predicates:
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
		if ordering is not None:
			name, direction = ordering
			order = f" ORDER BY {quote_identifier(name)} {direction.upper()}"
		limit = ""
		if count is not None:
			limit = " LIMIT ?"
			parameters.append(count)
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
		row: tuple[types.Scalar | None, ...],
	) -> T:
		expected = tuple(model_type.attrs)
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
				attribute = model_type.attrs[name]
				if raw_value is None:
					value = None
				else:
					value = attribute.type.decode(raw_value)
				attribute.check(value, model_type)
				values[name] = value
		except (TypeError, ValueError, ModelError) as error:
			raise DatabaseError(
				"database row contains an invalid model value"
			) from error

		identifier = cast(UUID, values["id"])
		existing = self.identity.get((model_type, identifier))
		if existing is not None:
			return cast(T, existing)
		model = cast(T, model_type.hydrate(values))
		self.identity[(model_type, identifier)] = model
		return model

	def attribute[T: Model](
		self, model_type: type[T], name: str
	) -> Attribute[Any, Any]:
		try:
			return model_type.attrs[name]
		except KeyError:
			raise ModelError(
				f"{model_type.__name__} has no attribute {name!r}"
			) from None

	def encode[T: Model](self, model_type: type[T], name: str, value: Any):
		attribute = model_type.attrs[name]
		if value is None:
			attribute.check(value, model_type)
			return None
		attribute.check(value, model_type)
		return types.encode(attribute.type, value)
