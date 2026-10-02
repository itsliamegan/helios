from collections.abc import Mapping
from typing import Any, Self, TYPE_CHECKING

from .clause import Clause
from .error import ModelError
from .model import Model
from .parser import ConditionParser
from .statement import ColumnReference, Count, Direction, Select

if TYPE_CHECKING:
	from .store import Store


class Query[T: Model]:
	def __init__(self, store: Store, model_type: type[T]):
		self.store = store
		self.model_type = model_type
		self.parser = ConditionParser(store.registry, model_type)
		self.clauses: list[Clause] = []
		self.ordering: list[tuple[str, Direction]] = []
		self.count: int | None = None

	def where(self, conditions: Mapping[str, Any]) -> Self:
		self.clauses.append(Clause((self.parser.parse(conditions),)))
		return self

	def where_not(self, conditions: Mapping[str, Any]) -> Self:
		group = self.parser.parse(conditions)
		self.clauses.append(Clause((group,), negated=True))
		return self

	def where_any(self, *groups: Mapping[str, Any]) -> Self:
		if not groups:
			raise ModelError(
				f"Query on {self.model_type.__name__} has where_any with no groups"
			)
		parsed = tuple(self.parser.parse(group) for group in groups)
		self.clauses.append(Clause(parsed))
		return self

	def order_by(self, name: str, direction: Direction = "asc") -> Self:
		self.model_type.column(name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		self.ordering.append((name, direction))
		return self

	def limit(self, count: int) -> Self:
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
		column = self.model_type.column(name)
		if self.count is not None:
			raise ModelError(
				f"Query on {self.model_type.__name__} cannot count_by with a limit"
			)
		statement = Select(
			table=self.model_type.table,
			columns=(ColumnReference(name), Count()),
			where=tuple(self.clauses),
			group_by=(name,),
		)
		return self.store.counts(column, statement)

	def exists(self) -> bool:
		statement = Select(
			table=self.model_type.table,
			columns=(ColumnReference("id"),),
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
			columns=tuple(ColumnReference(name) for name in self.model_type.columns),
			where=tuple(self.clauses),
			ordering=tuple(self.ordering),
			limit=limit,
		)
