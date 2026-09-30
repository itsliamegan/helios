from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, TypeIs

from .attribute import Attribute
from .codec import Scalar, encode
from .error import ModelError
from .model import Model

MALFORMED = "is not of the form 'name' or 'name operator'"


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False


@dataclass
class Group:
	conditions: tuple[Condition, ...]

	@classmethod
	def parse(cls, model_type: type[Model], conditions: dict[str, Any]) -> Group:
		subject = f"Query on {model_type.__name__}"
		if not isinstance(conditions, dict):
			raise ModelError(
				f"{subject} takes a dict of conditions, got {type(conditions).__name__}"
			)
		if not conditions:
			raise ModelError(f"{subject} has an empty condition group")

		parsed: list[Condition] = []
		for text, value in conditions.items():
			if not isinstance(text, str):
				raise ModelError(f"{subject} has {text!r}, which {MALFORMED}")
			try:
				key = Key.parse(text)
			except ValueError as error:
				raise ModelError(f"{subject} has {text!r}, which {error}") from error

			attribute = model_type.attribute(key.name)
			try:
				parsed.append(key.condition(attribute, value))
			except (TypeError, ValueError) as error:
				raise ModelError(
					f"{subject} has an invalid value for {text!r}: {error}"
				) from error
		return cls(tuple(parsed))


@dataclass
class Key:
	name: str
	operator: Operator | Literal["in"]

	@classmethod
	def parse(cls, text: str) -> Key:
		parts = text.split(" ")
		if not 1 <= len(parts) <= 2 or not all(parts):
			raise ValueError(MALFORMED)
		elif len(parts) == 1:
			return cls(parts[0], "=")
		elif is_operator(parts[1]):
			return cls(parts[0], parts[1])
		else:
			raise ValueError("has an unknown operator")

	def condition(self, attribute: Attribute, value: object) -> Condition:
		operator = self.operator
		match operator:
			case "in":
				return Membership.parse(attribute, value)
			case "=" if value is None:
				return IsNull.parse(attribute)
			case _:
				return Comparison.parse(attribute, operator, value)


type Condition = Comparison | IsNull | Membership


@dataclass
class Comparison:
	name: str
	operator: Operator
	value: Scalar

	@classmethod
	def parse(
		cls, attribute: Attribute, operator: Operator, value: object
	) -> Comparison:
		if value is None:
			raise ValueError("cannot compare with None")

		attribute.check(value)
		return cls(attribute.name, operator, encode(attribute.codec, value))


@dataclass
class IsNull:
	name: str

	@classmethod
	def parse(cls, attribute: Attribute) -> IsNull:
		attribute.check(None)
		return cls(attribute.name)


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool

	@classmethod
	def parse(cls, attribute: Attribute, value: object) -> Membership:
		if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
			raise TypeError(
				"expected an iterable other than str or bytes, "
				f"got {type(value).__name__}"
			)

		members = list(value)
		for member in members:
			attribute.check(member)
		values = tuple(
			dict.fromkeys(
				encode(attribute.codec, member)
				for member in members
				if member is not None
			)
		)
		return cls(attribute.name, values, None in members)


type Operator = Literal["=", "<", "<=", ">", ">="]
OPERATORS = ("=", "<", "<=", ">", ">=", "in")


def is_operator(text: str) -> TypeIs[Operator | Literal["in"]]:
	return text in OPERATORS
