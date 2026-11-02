from collections.abc import Mapping
from typing import Any, Self, TYPE_CHECKING

from .condition import AnyOf
from .error import ModelError
from .model import Model
from .parser import ConditionParser
from .statement import ColumnReference, Count, Direction, Order, Select

if TYPE_CHECKING:
	from .store import Store


class Query[T: Model]:
	"""Builds and runs a select over one model's table.

	Building methods change the query and return it. Running it leaves it
	unchanged, so it can run again.

	Each `where`, `where_not`, and `where_any` call adds a clause, and a row
	must meet every clause. Each clause takes a mapping of condition keys to
	values.

	A condition key is a column name, optionally followed by a space and one of
	the operators `=`, `<`, `<=`, `>`, `>=`, or `in`, as in `"rank <"`. A dotted
	key, as in `"author.name"`, follows relationships to a related model's
	column, and keys in one mapping under the same relationship match the same
	related row. `None` matches null with `=` and as a member of an `in` list.
	"""

	def __init__(self, store: Store, model_type: type[T]):
		self.store = store
		self.model_type = model_type
		self.parser = ConditionParser(store.registry, model_type)
		self.clauses: list[AnyOf] = []
		self.orders: list[Order] = []
		self.count: int | None = None

	def where(self, conditions: Mapping[str, Any]) -> Self:
		"""Keep the rows that meet every condition."""

		self.clauses.append(AnyOf((self.parser.parse(conditions),)))
		return self

	def where_not(self, conditions: Mapping[str, Any]) -> Self:
		"""Keep exactly the rows that `where` with the same conditions would not.

		A row whose column is null for a comparison is kept, unlike with SQL's
		`NOT`. Under a relationship, a row is kept when no related row meets the
		conditions.
		"""

		group = self.parser.parse(conditions)
		self.clauses.append(AnyOf((group,), negated=True))
		return self

	def where_any(self, *groups: Mapping[str, Any]) -> Self:
		"""Keep the rows that meet every condition in at least one group."""

		if not groups:
			raise ModelError(
				f"Query on {self.model_type.__name__} has where_any with no groups"
			)
		parsed = tuple(self.parser.parse(group) for group in groups)
		self.clauses.append(AnyOf(parsed))
		return self

	def order_by(self, name: str, direction: Direction = "asc") -> Self:
		"""Sort by a column, after any earlier orders."""

		self.model_type.column(name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		self.orders.append(Order(name, direction))
		return self

	def limit(self, count: int) -> Self:
		"""Keep at most `count` rows, replacing any earlier limit."""

		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		self.count = count
		return self

	def all(self) -> list[T]:
		"""Return the matching models, in no particular order unless sorted."""

		return self.store.models(self.model_type, self.select(self.count))

	def first(self) -> T | None:
		"""Return the first matching model, or `None` when nothing matches."""

		found = self.store.models(self.model_type, self.select(self.at_most_one))
		return found[0] if found else None

	def count_by(self, name: str) -> dict[Any, int]:
		"""Count rows by a column's value, leaving out values with no rows.

		The query's sort keys do not apply, and a query with a limit cannot
		count.
		"""

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
		"""Return whether any row matches."""

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
			order_by=tuple(self.orders),
			limit=limit,
		)
