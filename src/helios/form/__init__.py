from typing import Any

from helios.http import Input

from . import parser


class Field:
	def __init__(self, name: str, parser: parser.Parser[Any]):
		self.name = name
		self.parser = parser

	def validate(self, input: Input) -> tuple[Any, list[str]]:
		try:
			raw = input[self.name]
		except KeyError:
			raw = None

		try:
			return self.parser.parse(raw), []
		except parser.ParseError as error:
			return None, [str(error)]


class Form:
	def __init__(self, fields: list[Field]):
		self.fields = fields

	def validate(
		self,
		input: Input,
	) -> tuple[dict[str, Any], dict[str, list[str]]]:
		data: dict[str, Any] = {}
		errors: dict[str, list[str]] = {}
		for field in self.fields:
			value, field_errors = field.validate(input)
			if field_errors:
				errors[field.name] = field_errors
			else:
				data[field.name] = value
		return data, errors
