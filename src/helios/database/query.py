from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from .attribute import Attribute
from .codec import Scalar, encode
from .error import ModelError
from .model import Model

if TYPE_CHECKING:
	from .store import Store


type Direction = Literal["asc", "desc"]
type Operator = Literal["=", "<", "<=", ">", ">="]

COMPARISONS = ("=", "<", "<=", ">", ">=")
ORDERINGS = ("<", "<=", ">", ">=")


@dataclass
class Comparison:
	name: str
	operator: Operator
	value: Scalar | None


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool


type Condition = Comparison | Membership
type Group = tuple[Condition, ...]


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False


def group(model_type: type[Model], conditions: object) -> Group:
	subject = f"Query on {model_type.__name__}"
	if not isinstance(conditions, dict):
		raise ModelError(
			f"{subject} takes a dictionary of conditions, "
			f"got {type(conditions).__name__}"
		)
	if not conditions:
		raise ModelError(f"{subject} has an empty condition group")
	return tuple(condition(model_type, key, value) for key, value in conditions.items())


def condition(model_type: type[Model], key: object, value: object) -> Condition:
	subject = f"Query on {model_type.__name__}"
	parts = key.split(" ") if isinstance(key, str) else []
	if not 1 <= len(parts) <= 2 or not all(parts):
		raise ModelError(f"{subject} has {key!r}, which is not a condition key")
	name, operator = parts if len(parts) == 2 else (parts[0], "=")
	if operator not in (*COMPARISONS, "in"):
		raise ModelError(f"{subject} has {key!r}, which has an unknown operator")
	attribute = model_type.attribute(name)

	def invalid(reason: str) -> ModelError:
		return ModelError(f"{subject} has an invalid value for {key!r}: {reason}")

	if operator == "in":
		if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
			raise invalid(
				"expected an iterable other than str or bytes, "
				f"got {type(value).__name__}"
			)
		encoded: list[Scalar | None] = []
		for member in value:
			problem = attribute.problem(member)
			if problem is not None:
				raise invalid(problem)
			encoded.append(encoded_value(attribute, member))
		values = tuple(dict.fromkeys(item for item in encoded if item is not None))
		return Membership(name, values, None in encoded)
	if value is None and operator in ORDERINGS:
		raise invalid("cannot compare with None")
	problem = attribute.problem(value)
	if problem is not None:
		raise invalid(problem)
	return Comparison(name, operator, encoded_value(attribute, value))


def encoded_value(attribute: Attribute, value: object) -> Scalar | None:
	return None if value is None else encode(attribute.codec, value)


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	clauses: tuple[Clause, ...] = ()
	ordering: tuple[str, Direction] | None = None
	_limit: int | None = None

	def where(self, conditions: dict[str, Any]) -> Query[T]:
		return self.adding(Clause((group(self.model_type, conditions),)))

	def where_not(self, conditions: dict[str, Any]) -> Query[T]:
		clause = Clause((group(self.model_type, conditions),), negated=True)
		return self.adding(clause)

	def where_any(self, *groups: dict[str, Any]) -> Query[T]:
		if not groups:
			raise ModelError(
				f"Query on {self.model_type.__name__} has where_any with no groups"
			)
		clause = Clause(tuple(group(self.model_type, each) for each in groups))
		return self.adding(clause)

	def adding(self, clause: Clause) -> Query[T]:
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=(*self.clauses, clause),
			ordering=self.ordering,
			_limit=self._limit,
		)

	def order_by(self, name: str, direction: Direction = "asc") -> Query[T]:
		self.model_type.attribute(name)
		if direction not in ("asc", "desc"):
			raise ValueError("direction must be 'asc' or 'desc'")
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=self.clauses,
			ordering=(name, direction),
			_limit=self._limit,
		)

	def limit(self, count: int) -> Query[T]:
		if not isinstance(count, int) or isinstance(count, bool) or count < 0:
			raise ValueError("limit must be a non-negative integer")
		return Query(
			store=self.store,
			model_type=self.model_type,
			clauses=self.clauses,
			ordering=self.ordering,
			_limit=count,
		)

	def all(self) -> list[T]:
		return self.store.execute(self)

	def first(self) -> T | None:
		found = self.limit(0 if self._limit == 0 else 1).all()
		return found[0] if found else None
