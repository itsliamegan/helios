from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from .codec import Scalar
from .model import Model

if TYPE_CHECKING:
	from .store import Store


type Direction = Literal["asc", "desc"]


@dataclass
class Filter:
	name: str
	value: Scalar | None


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool


type Predicate = Filter | Membership


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	predicates: tuple[Predicate, ...] = ()
	ordering: tuple[str, Direction] | None = None
	count: int | None = None

	def where(self, **attributes: Any) -> Query[T]:
		predicates = list(self.predicates)
		for name, value in attributes.items():
			attribute = self.model_type.attribute(name)
			predicates.append(Filter(name, attribute.encode(value, self.model_type)))
		return Query(
			self.store,
			self.model_type,
			tuple(predicates),
			self.ordering,
			self.count,
		)

	def where_in(self, **attributes: Iterable[Any]) -> Query[T]:
		predicates = list(self.predicates)
		for name, candidates in attributes.items():
			if isinstance(candidates, (str, bytes)) or not isinstance(
				candidates, Iterable
			):
				raise TypeError(
					f"where_in({name!r}=...) requires an iterable of candidates, "
					f"got {type(candidates).__name__}"
				)
			attribute = self.model_type.attribute(name)
			encoded = [
				attribute.encode(candidate, self.model_type) for candidate in candidates
			]
			values = tuple(
				dict.fromkeys(value for value in encoded if value is not None)
			)
			predicates.append(Membership(name, values, None in encoded))
		return Query(
			self.store,
			self.model_type,
			tuple(predicates),
			self.ordering,
			self.count,
		)

	def order_by(self, name: str, direction: Direction = "asc") -> Query[T]:
		self.model_type.attribute(name)
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
		return self.store.execute(self)

	def first(self) -> T | None:
		found = self.limit(0 if self.count == 0 else 1).all()
		return found[0] if found else None
