from dataclasses import replace
from typing import Any, ClassVar, Self, dataclass_transform

from luna.inflect import sentence

from helios.declaration import DeclarationError, check_keywords, declared
from helios.http import Input

from .error import FormError
from .errors import Errors
from .field import Failure, Field, declare
from .rule import Rule


@dataclass_transform(kw_only_default=True, eq_default=False)
class Form:
	fields: ClassVar[dict[str, Field]] = {}
	rules: ClassVar[dict[str, list[Rule[Any, Any]]]] = {}
	messages: ClassVar[dict[str, str]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		fields = {}
		for name, field in cls.fields.items():
			fields[name] = replace(field, extra_rules=cls.rules.get(name, []))

		try:
			for entry in declared(cls):
				if entry.name in RESERVED:
					raise FormError(
						f"Form {cls.__name__} has a field named '{entry.name}', "
						"which Form uses"
					)
				if entry.pending:
					entry = entry.resolve()
				field = declare(entry, cls.rules.get(entry.name, []))
				setattr(cls, entry.name, field)
				fields[entry.name] = field
		except DeclarationError as error:
			raise FormError(f"{cls.__name__}.{error}") from error

		for name in cls.rules:
			if name not in fields:
				raise FormError(
					f"Form {cls.__name__} has rules for '{name}', which is not a field"
				)
		cls.fields = fields

	def __init__(self, **values: Any):
		form = type(self)
		check_keywords(
			form,
			"fields",
			values,
			form.fields,
			[name for name, field in form.fields.items() if field.required],
		)

		self.values: dict[str, Any] = {}
		for name, field in form.fields.items():
			self.values[name] = values.get(name, field.initial)

	@classmethod
	def validate(cls, input: Input) -> tuple[Self, Errors]:
		form = cls.__new__(cls)
		form.values = {}
		errors = Errors()
		for name, field in cls.fields.items():
			try:
				form.values[name] = field.validate(input)
			except Failure as failure:
				errors.add(name, cls.message(name, failure))
		return form, errors

	@classmethod
	def message(cls, name: str, failure: Failure) -> str:
		key = f"{name}.{failure.rule}"
		if key in cls.messages:
			return cls.messages[key]
		else:
			return f"{sentence(name)} {failure.message}."

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={self.values[name]!r}"
			for name in type(self).fields
			if name in self.values
		)
		return f"{type(self).__name__}({values})"


RESERVED = {"values", *vars(Form)}
