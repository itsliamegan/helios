from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from . import types
from .model import Model

if TYPE_CHECKING:
	from .store import Store


type Direction = Literal["asc", "desc"]


@dataclass
class Filter:
	name: str
	value: types.Scalar | None


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	filters: tuple[Filter, ...] = ()
	ordering: tuple[str, Direction] | None = None
	count: int | None = None

	def where(self, **attrs: Any) -> Query[T]:
		filters = list(self.filters)
		for name, value in attrs.items():
			attribute = self.store.attribute(self.model_type, name)
			attribute.check(value, self.model_type)
			encoded = None if value is None else types.encode(attribute.type, value)
			filters.append(Filter(name, encoded))
		return Query(
			self.store,
			self.model_type,
			tuple(filters),
			self.ordering,
			self.count,
		)

	def order_by(self, name: str, direction: Direction = "asc") -> Query[T]:
		self.store.attribute(self.model_type, name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		return Query(
			self.store,
			self.model_type,
			self.filters,
			(name, direction),
			self.count,
		)

	def limit(self, count: int) -> Query[T]:
		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		return Query(
			self.store,
			self.model_type,
			self.filters,
			self.ordering,
			count,
		)

	def all(self) -> list[T]:
		return self.store.execute_query(
			self.model_type,
			self.filters,
			self.ordering,
			self.count,
		)

	def first(self) -> T | None:
		count = 0 if self.count == 0 else 1
		found = self.store.execute_query(
			self.model_type,
			self.filters,
			self.ordering,
			count,
		)
		return found[0] if found else None
