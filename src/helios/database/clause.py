from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TypeIs

from .codec import Scalar, encode
from .column import Column
from .error import ModelError
from .model import Model
from .registry import Registry


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False


@dataclass
class Group:
	conditions: tuple[Condition, ...]

	@classmethod
	def parse(
		cls,
		registry: Registry,
		model_type: type[Model],
		conditions: dict[str, Any],
	) -> Group:
		subject = f"Query on {model_type.__name__}"
		if not conditions:
			raise ModelError(f"{subject} has an empty condition group")

		terms: list[Term] = []
		for text, value in conditions.items():
			try:
				key = Key.parse(text)
			except ValueError as error:
				raise ModelError(f"{subject} has {text!r}, which {error}") from error
			terms.append(Term(text, key, value))
		return cls.build(registry, model_type, subject, terms, 0)

	@classmethod
	def build(
		cls,
		registry: Registry,
		model_type: type[Model],
		subject: str,
		terms: list[Term],
		depth: int,
	) -> Group:
		parsed: list[Condition | str] = []
		nested: dict[str, list[Term]] = {}
		for term in terms:
			name = term.key.path[depth]
			if depth < len(term.key.path) - 1:
				if name not in model_type.relationships:
					raise ModelError(
						f"{subject} has {term.text!r}, "
						f"where {model_type.__name__}.{name} is not a relationship"
					)
				if name not in nested:
					nested[name] = []
					parsed.append(name)
				nested[name].append(term)
				continue

			column = model_type.columns.get(name)
			if column is None:
				raise ModelError(
					f"{subject} has {term.text!r}, "
					f"where {model_type.__name__}.{name} is not a column"
				)
			try:
				parsed.append(term.key.condition(column, term.value))
			except (TypeError, ValueError) as error:
				raise ModelError(
					f"{subject} has an invalid value for {term.text!r}: {error}"
				) from error

		conditions: list[Condition] = []
		for item in parsed:
			if isinstance(item, str):
				relationship = model_type.relationships[item]
				target = registry.get(relationship.target)
				group = cls.build(registry, target, subject, nested[item], depth + 1)
				item = Exists(
					target.table,
					relationship.target_column,
					relationship.owner_column,
					group,
				)
			conditions.append(item)
		return cls(tuple(conditions))


@dataclass
class Term:
	text: str
	key: Key
	value: object


@dataclass
class Key:
	path: tuple[str, ...]
	operator: Operator | Literal["in"]

	@classmethod
	def parse(cls, text: str) -> Key:
		parts = text.split(" ")
		if not 1 <= len(parts) <= 2 or not all(parts):
			raise ValueError("is not of the form 'name' or 'name operator'")

		path = tuple(parts[0].split("."))
		if not all(path):
			raise ValueError("is not of the form 'name' or 'name operator'")
		elif len(parts) == 1:
			return cls(path, "=")
		elif is_operator(parts[1]):
			return cls(path, parts[1])
		else:
			raise ValueError("has an unknown operator")

	def condition(self, column: Column, value: object) -> Condition:
		operator = self.operator
		match operator:
			case "in":
				return Membership.parse(column, value)
			case "=" if value is None:
				return IsNull.parse(column)
			case _:
				return Comparison.parse(column, operator, value)


type Condition = Comparison | IsNull | Membership | Exists


@dataclass
class Comparison:
	name: str
	operator: Operator
	value: Scalar

	@classmethod
	def parse(cls, column: Column, operator: Operator, value: object) -> Comparison:
		if value is None:
			raise ValueError("cannot compare with None")

		column.check(value)
		return cls(column.name, operator, encode(column.codec, value))


@dataclass
class IsNull:
	name: str

	@classmethod
	def parse(cls, column: Column) -> IsNull:
		column.check(None)
		return cls(column.name)


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool

	@classmethod
	def parse(cls, column: Column, value: object) -> Membership:
		if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
			raise TypeError(
				"expected an iterable other than str or bytes, "
				f"got {type(value).__name__}"
			)

		members = list(value)
		for member in members:
			column.check(member)
		values = tuple(
			dict.fromkeys(
				encode(column.codec, member) for member in members if member is not None
			)
		)
		return cls(column.name, values, None in members)


@dataclass
class Exists:
	table: str
	column: str
	outer_column: str
	group: Group


type Operator = Literal["=", "<", "<=", ">", ">="]
OPERATORS = ("=", "<", "<=", ">", ">=", "in")


def is_operator(text: str) -> TypeIs[Operator | Literal["in"]]:
	return text in OPERATORS
