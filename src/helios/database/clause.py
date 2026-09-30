from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .codec import Scalar, encode
from .error import ModelError
from .key import Key
from .model import Model

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
		if key.operator not in (*COMPARISONS, "in"):
			raise ModelError(f"{subject} has {text!r}, which has an unknown operator")
		attribute = model_type.attribute(key.name)

		def invalid(reason: object) -> ModelError:
			return ModelError(f"{subject} has an invalid value for {text!r}: {reason}")

		if key.operator == "in":
			if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
				raise invalid(
					"expected an iterable other than str or bytes, "
					f"got {type(value).__name__}"
				)
			members = list(value)
			for member in members:
				try:
					attribute.check(member)
				except (TypeError, ValueError) as error:
					raise invalid(error) from error
			values = tuple(
				dict.fromkeys(
					encode(attribute.codec, member)
					for member in members
					if member is not None
				)
			)
			return Membership(key.name, values, None in members)
		if value is None and key.operator in ORDERINGS:
			raise invalid("cannot compare with None")
		try:
			attribute.check(value)
		except (TypeError, ValueError) as error:
			raise invalid(error) from error
		if value is None:
			return IsNull(key.name)
		else:
			return Comparison(key.name, key.operator, encode(attribute.codec, value))


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False
