from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, TypeIs

from .attribute import Attribute
from .codec import Scalar, encode
from .error import ModelError
from .key import Key
from .model import Model

type Operator = Literal["=", "<", "<=", ">", ">="]

OPERATORS = ("=", "<", "<=", ">", ">=", "in")


def is_operator(text: str) -> TypeIs[Operator | Literal["in"]]:
	return text in OPERATORS


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False


@dataclass
class Group:
	conditions: tuple[Condition, ...]

	@classmethod
	def parse(cls, model_type: type[Model], conditions: object) -> Group:
		subject = f"Query on {model_type.__name__}"
		if not isinstance(conditions, dict):
			raise ModelError(
				f"{subject} takes a dict of conditions, got {type(conditions).__name__}"
			)
		if not conditions:
			raise ModelError(f"{subject} has an empty condition group")

		return cls(
			tuple(
				cls.condition(model_type, text, value)
				for text, value in conditions.items()
			)
		)

	@staticmethod
	def condition(model_type: type[Model], text: object, value: object) -> Condition:
		subject = f"Query on {model_type.__name__}"
		key = Key.parse(text) if isinstance(text, str) else None
		if key is None:
			raise ModelError(
				f"{subject} has {text!r}, "
				"which is not of the form 'name' or 'name operator'"
			)
		operator = key.operator
		if not is_operator(operator):
			raise ModelError(f"{subject} has {text!r}, which has an unknown operator")

		attribute = model_type.attribute(key.name)
		try:
			match operator:
				case "in":
					return Membership.parse(attribute, value)
				case "=" if value is None:
					return IsNull.parse(attribute)
				case _:
					return Comparison.parse(attribute, operator, value)
		except (TypeError, ValueError) as error:
			raise ModelError(
				f"{subject} has an invalid value for {text!r}: {error}"
			) from error


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
