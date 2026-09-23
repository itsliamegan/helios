from __future__ import annotations

from collections.abc import Iterable
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
class Membership:
	name: str
	values: tuple[types.Scalar, ...]
	includes_null: bool


type Predicate = Filter | Membership


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	predicates: tuple[Predicate, ...] = ()
	ordering: tuple[str, Direction] | None = None
	count: int | None = None

	def where(self, **attrs: Any) -> Query[T]:
		predicates = list(self.predicates)
		for name, value in attrs.items():
			attribute = self.store.attribute(self.model_type, name)
			attribute.check(value, self.model_type)
			encoded = None if value is None else types.encode(attribute.type, value)
			predicates.append(Filter(name, encoded))
		return Query(
			self.store,
			self.model_type,
			tuple(predicates),
			self.ordering,
			self.count,
		)

	def where_in(self, **attrs: Iterable[Any]) -> Query[T]:
		predicates = list(self.predicates)
		for name, candidates in attrs.items():
			if isinstance(candidates, (str, bytes)) or not isinstance(
				candidates, Iterable
			):
				raise TypeError(
					f"where_in({name!r}=...) requires an iterable of candidates, "
					f"got {type(candidates).__name__}"
				)
			attribute = self.store.attribute(self.model_type, name)
			includes_null = False
			values: list[types.Scalar] = []
			seen: set[types.Scalar] = set()
			for candidate in candidates:
				attribute.check(candidate, self.model_type)
				if candidate is None:
					includes_null = True
					continue
				encoded = types.encode(attribute.type, candidate)
				if encoded not in seen:
					seen.add(encoded)
					values.append(encoded)
			predicates.append(Membership(name, tuple(values), includes_null))
		return Query(
			self.store,
			self.model_type,
			tuple(predicates),
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
			self.predicates,
			(name, direction),
			self.count,
		)

	def limit(self, count: int) -> Query[T]:
		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		return Query(
			self.store,
			self.model_type,
			self.predicates,
			self.ordering,
			count,
		)

	def all(self) -> list[T]:
		return self.store.execute_query(
			self.model_type,
			self.predicates,
			self.ordering,
			self.count,
		)

	def first(self) -> T | None:
		count = 0 if self.count == 0 else 1
		found = self.store.execute_query(
			self.model_type,
			self.predicates,
			self.ordering,
			count,
		)
		return found[0] if found else None
