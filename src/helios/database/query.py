from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .clause import Clause, Group
from .error import ModelError
from .model import Model
from .statement import Column, Count, Direction, Select

if TYPE_CHECKING:
	from .store import Store


class Query[T: Model]:
	def __init__(self, store: Store, model_type: type[T]):
		self.store = store
		self.model_type = model_type
		self.clauses: list[Clause] = []
		self.ordering: list[tuple[str, Direction]] = []
		self.count: int | None = None

	def where(self, conditions: dict[str, Any]) -> Query[T]:
		self.clauses.append(Clause((Group.parse(self.model_type, conditions),)))
		return self

	def where_not(self, conditions: dict[str, Any]) -> Query[T]:
		group = Group.parse(self.model_type, conditions)
		self.clauses.append(Clause((group,), negated=True))
		return self

	def where_any(self, *groups: dict[str, Any]) -> Query[T]:
		if not groups:
			raise ModelError(
				f"Query on {self.model_type.__name__} has where_any with no groups"
			)
		parsed = tuple(Group.parse(self.model_type, group) for group in groups)
		self.clauses.append(Clause(parsed))
		return self

	def order_by(self, name: str, direction: Direction = "asc") -> Query[T]:
		self.model_type.attribute(name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		self.ordering.append((name, direction))
		return self

	def limit(self, count: int) -> Query[T]:
		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		self.count = count
		return self

	def all(self) -> list[T]:
		return self.store.models(self.model_type, self.select(self.count))

	def first(self) -> T | None:
		found = self.store.models(self.model_type, self.select(self.at_most_one))
		return found[0] if found else None

	def count_by(self, name: str) -> dict[Any, int]:
		attribute = self.model_type.attribute(name)
		if self.count is not None:
			raise ModelError(
				f"Query on {self.model_type.__name__} cannot count_by with a limit"
			)
		statement = Select(
			table=self.model_type.table,
			columns=(Column(name), Count()),
			where=tuple(self.clauses),
			group_by=(name,),
		)
		return self.store.counts(attribute, statement)

	def exists(self) -> bool:
		statement = Select(
			table=self.model_type.table,
			columns=(Column("id"),),
			where=tuple(self.clauses),
			limit=self.at_most_one,
		)
		return self.store.has_rows(statement)

	@property
	def at_most_one(self) -> int:
		return 0 if self.count == 0 else 1

	def select(self, limit: int | None) -> Select:
		return Select(
			table=self.model_type.table,
			columns=tuple(Column(name) for name in self.model_type.attributes),
			where=tuple(self.clauses),
			ordering=tuple(self.ordering),
			limit=limit,
		)
