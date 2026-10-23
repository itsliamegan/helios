from dataclasses import dataclass

from helios.http import Input

from .errors import Errors

COLLECTIONS = (list, tuple, set, frozenset)


@dataclass(init=False)
class Submission:
	"""The input and errors flashed by the last failed submission."""

	input: Input | None
	errors: Errors

	def __init__(self, input: Input | None = None, errors: Errors | None = None):
		self.input = input
		self.errors = errors if errors is not None else Errors()

	def value(self, name: str, default: object = "") -> str | list[str]:
		if self.input is None:
			# Nothing was flashed, so the form renders from its defaults.
			return encode(default)

		if isinstance(default, COLLECTIONS):
			return self.input.all(name)
		else:
			# A field missing from flashed input was submitted empty, as an
			# unchecked checkbox is, so it does not fall back to its default.
			return self.input.first(name) or ""

	def error(self, name: str) -> str | None:
		return self.errors.first(name)

	def invalid(self, name: str) -> bool:
		return self.error(name) is not None


def encode(value: object) -> str | list[str]:
	if isinstance(value, COLLECTIONS):
		return [encode_item(item) for item in value]
	else:
		return encode_item(value)


def encode_item(value: object) -> str:
	if value is None:
		return ""
	if isinstance(value, bool):
		return "on" if value else ""
	if isinstance(value, str):
		return value
	return str(value)
