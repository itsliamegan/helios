from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from .codec import Scalar, encode
from .error import ModelError
from .key import Key
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
	value: Scalar


@dataclass
class IsNull:
	name: str


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool


type Condition = Comparison | IsNull | Membership
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


def condition(model_type: type[Model], text: object, value: object) -> Condition:
	subject = f"Query on {model_type.__name__}"
	key = Key.parse(text)
	if key is None:
		raise ModelError(f"{subject} has {text!r}, which is not a condition key")
	name, operator = key.name, key.operator
	if operator not in (*COMPARISONS, "in"):
		raise ModelError(f"{subject} has {text!r}, which has an unknown operator")
	attribute = model_type.attribute(name)

	def invalid(reason: str) -> ModelError:
		return ModelError(f"{subject} has an invalid value for {text!r}: {reason}")

	if operator == "in":
		if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
			raise invalid(
				"expected an iterable other than str or bytes, "
				f"got {type(value).__name__}"
			)
		members = list(value)
		for member in members:
			problem = attribute.problem(member)
			if problem is not None:
				raise invalid(problem)
		values = tuple(
			dict.fromkeys(
				encode(attribute.codec, member)
				for member in members
				if member is not None
			)
		)
		return Membership(name, values, None in members)
	if value is None and operator in ORDERINGS:
		raise invalid("cannot compare with None")
	problem = attribute.problem(value)
	if problem is not None:
		raise invalid(problem)
	elif value is None:
		return IsNull(name)
	else:
		return Comparison(name, operator, encode(attribute.codec, value))


@dataclass
class Query[T: Model]:
	store: Store
	model_type: type[T]
	clauses: tuple[Clause, ...] = ()
	ordering: tuple[tuple[str, Direction], ...] = ()
	count: int | None = None

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
