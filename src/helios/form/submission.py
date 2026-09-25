from dataclasses import dataclass

from helios.http import Input

from .errors import Errors

COLLECTIONS = (list, tuple, set, frozenset)


@dataclass(init=False)
class Submission:
	input: Input | None
	errors: Errors

	def __init__(self, input: Input | None = None, errors: Errors | None = None):
		self.input = input
		self.errors = errors if errors is not None else Errors()

	def value(self, name: str, default: object = "") -> str | list[str]:
		collection = isinstance(default, COLLECTIONS)
		if self.input is None:
			return encode(default)
		if name not in self.input:
			return [] if collection else ""
		value = self.input[name]
		if collection and isinstance(value, str):
			return [value]
		return value

	def error(self, name: str) -> str | None:
		return self.errors.first(name)

	def invalid(self, name: str) -> bool:
		return self.error(name) is not None


def encode(value: object) -> str | list[str]:
	if isinstance(value, COLLECTIONS):
		return [encode_item(item) for item in value]
	return encode_item(value)


def encode_item(value: object) -> str:
	if value is None:
		return ""
	if isinstance(value, bool):
		return "on" if value else ""
	if isinstance(value, str):
		return value
	return str(value)
