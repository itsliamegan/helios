from collections.abc import Callable
from typing import Any

Rule = Callable[[Any], str | None]

class Field:
	def __init__(self, name: str, rules: list[Rule]):
		self.name = name
		self.rules = rules

	def validate(self, input: dict[str, Any]) -> tuple[Any, list[str]]:
		if self.name in input:
			val = input[self.name]
		else:
			val = None
		errs = []
		for rule in self.rules:
			err = rule(val)
			if err is not None:
				errs.append(err)
		return val, errs

class Form:
	def __init__(self, fields: list[Field]):
		self.fields = fields

	def validate(self, input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[str]]]:
		data = {}
		errs = {}
		for field in self.fields:
			val, err = field.validate(input)
			if len(err) != 0:
				errs[field.name] = err
			else:
				data[field.name] = val
		return data, errs
