from dataclasses import dataclass
from typing import Any, Literal, TypeIs

from .clause import Comparison, Condition, Exists, Group, IsNull, Membership, Operator
from .column import Column
from .error import ModelError
from .model import Model
from .registry import Registry


class ConditionParser:
	def __init__(self, registry: Registry, model_type: type[Model]):
		self.registry = registry
		self.model_type = model_type
		self.subject = f"Query on {model_type.__name__}"

	def parse(self, conditions: dict[str, Any]) -> Group:
		if not conditions:
			raise ModelError(f"{self.subject} has an empty condition group")

		terms: list[Term] = []
		for text, value in conditions.items():
			try:
				key = Key.parse(text)
			except ValueError as error:
				raise ModelError(
					f"{self.subject} has {text!r}, which {error}"
				) from error
			terms.append(Term(text, key, value))
		return self.build(self.model_type, terms, 0)

	def build(self, model_type: type[Model], terms: list[Term], depth: int) -> Group:
		conditions: list[Condition] = []
		for item in split(terms, depth):
			if isinstance(item, Term):
				conditions.append(self.compare(model_type, item, depth))
			else:
				conditions.append(self.exists(model_type, item, depth))
		return Group(tuple(conditions))

	def compare(self, model_type: type[Model], term: Term, depth: int) -> Condition:
		name = term.key.path[depth]
		column = model_type.columns.get(name)
		if column is None:
			raise ModelError(
				f"{self.subject} has {term.text!r}, "
				f"where {model_type.__name__}.{name} is not a column"
			)
		try:
			return term.key.condition(column, term.value)
		except (TypeError, ValueError) as error:
			raise ModelError(
				f"{self.subject} has an invalid value for {term.text!r}: {error}"
			) from error

	def exists(self, model_type: type[Model], terms: list[Term], depth: int) -> Exists:
		first = terms[0]
		name = first.key.path[depth]
		relationship = model_type.relationships.get(name)
		if relationship is None:
			raise ModelError(
				f"{self.subject} has {first.text!r}, "
				f"where {model_type.__name__}.{name} is not a relationship"
			)
		target = self.registry.get(relationship.target)
		return Exists(
			target.table,
			relationship.target_column,
			relationship.owner_column,
			self.build(target, terms, depth + 1),
		)


def split(terms: list[Term], depth: int) -> list[Term | list[Term]]:
	items: list[Term | list[Term]] = []
	nested: dict[str, list[Term]] = {}
	for term in terms:
		if depth == len(term.key.path) - 1:
			items.append(term)
			continue
		name = term.key.path[depth]
		if name not in nested:
			nested[name] = []
			items.append(nested[name])
		nested[name].append(term)
	return items


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


OPERATORS = ("=", "<", "<=", ">", ">=", "in")


def is_operator(text: str) -> TypeIs[Operator | Literal["in"]]:
	return text in OPERATORS
