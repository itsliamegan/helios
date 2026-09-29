from collections.abc import Iterable

from .clause import Group
from .codec import encode
from .condition import Comparison, Condition, IsNull, Membership
from .error import ModelError
from .key import Key
from .model import Model

COMPARISONS = ("=", "<", "<=", ">", ">=")
ORDERINGS = ("<", "<=", ">", ">=")


def parse(model_type: type[Model], conditions: object) -> Group:
	subject = f"Query on {model_type.__name__}"
	if not isinstance(conditions, dict):
		raise ModelError(
			f"{subject} takes a dictionary of conditions, "
			f"got {type(conditions).__name__}"
		)
	if not conditions:
		raise ModelError(f"{subject} has an empty condition group")
	return tuple(
		parse_condition(model_type, text, value) for text, value in conditions.items()
	)


def parse_condition(model_type: type[Model], text: object, value: object) -> Condition:
	subject = f"Query on {model_type.__name__}"
	key = Key.parse(text)
	if key is None:
		raise ModelError(f"{subject} has {text!r}, which is not a condition key")
	if key.operator not in (*COMPARISONS, "in"):
		raise ModelError(f"{subject} has {text!r}, which has an unknown operator")
	attribute = model_type.attribute(key.name)

	def invalid(reason: str) -> ModelError:
		return ModelError(f"{subject} has an invalid value for {text!r}: {reason}")

	if key.operator == "in":
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
		return Membership(key.name, values, None in members)
	if value is None and key.operator in ORDERINGS:
		raise invalid("cannot compare with None")
	problem = attribute.problem(value)
	if problem is not None:
		raise invalid(problem)
	elif value is None:
		return IsNull(key.name)
	else:
		return Comparison(key.name, key.operator, encode(attribute.codec, value))
