from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from .clause import Clause
from .error import ModelError
from .model import Model
from .parser import parse

if TYPE_CHECKING:
	from .store import Store


type Direction = Literal["asc", "desc"]


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	clauses: tuple[Clause, ...] = ()
	ordering: tuple[tuple[str, Direction], ...] = ()
	count: int | None = None

	def where(self, conditions: dict[str, Any]) -> Query[T]:
		return self.adding(Clause((parse(self.model_type, conditions),)))

	def where_not(self, conditions: dict[str, Any]) -> Query[T]:
		clause = Clause((parse(self.model_type, conditions),), negated=True)
		return self.adding(clause)

	def where_any(self, *groups: dict[str, Any]) -> Query[T]:
		if not groups:
			raise ModelError(
				f"Query on {self.model_type.__name__} has where_any with no groups"
			)
		clause = Clause(tuple(parse(self.model_type, each) for each in groups))
		return self.adding(clause)

	def adding(self, clause: Clause) -> Query[T]:
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=(*self.clauses, clause),
			ordering=self.ordering,
			count=self.count,
		)

	def order_by(self, name: str, direction: Direction = "asc") -> Query[T]:
		self.model_type.attribute(name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=self.clauses,
			ordering=(*self.ordering, (name, direction)),
			count=self.count,
		)

	def limit(self, count: int) -> Query[T]:
		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=self.clauses,
			ordering=self.ordering,
			count=count,
		)

	def all(self) -> list[T]:
		return self.store.execute(self)

	def first(self) -> T | None:
		found = self.limit(0 if self.count == 0 else 1).all()
		return found[0] if found else None

	def count_by(self, name: str) -> dict[Any, int]:
		self.model_type.attribute(name)
		if self.count is not None:
			raise ModelError(
				f"Query on {self.model_type.__name__} cannot count_by with a limit"
			)
		return self.store.execute_count_by(self, name)

	def exists(self) -> bool:
		return self.store.execute_exists(self)
