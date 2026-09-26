from typing import Any, ClassVar, Self, dataclass_transform

from luna.inflect import sentence, words

from helios.declarative import check_init_keywords, check_single_base, declarations
from helios.http import Input

from .error import FormError
from .errors import Errors
from .field import Failure, Field, INVALID, declare
from .filter import Filter
from .rule import Rule

ITEMS = "*"


@dataclass_transform(kw_only_default=True, eq_default=False)
class Form:
	fields: ClassVar[dict[str, Field]] = {}
	filters: ClassVar[dict[str, list[Filter[Any]]]] = {}
	rules: ClassVar[dict[str, list[Rule[Any]]]] = {}
	messages: ClassVar[dict[str, str]] = {}

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Form, FormError)
		cls.fields = {}
		for declaration in declarations(cls, declare, FormError):
			if declaration.name in RESERVED:
				raise FormError(
					f"Form {cls.__name__} has a field named '{declaration.name}', "
					"which Form uses"
				)
			field = declaration.resolve()
			cls.fields[declaration.name] = field
			setattr(cls, declaration.name, field)

		for key, filters in cls.filters.items():
			field, items = target(cls, "filters", key)
			if items:
				field.item_filters = filters
			else:
				field.filters = filters

		for key, rules in cls.rules.items():
			field, items = target(cls, "rules", key)
			if items:
				field.item_rules = rules
			else:
				field.rules = rules

	def __init__(self, **values: Any):
		form = type(self)
		check_init_keywords(
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
		if failure.item and failure.key != INVALID:
			key = f"{name}.{ITEMS}.{failure.key}"
		else:
			key = f"{name}.{failure.key}"

		if key in cls.messages:
			return cls.messages[key]
		elif failure.item:
			return f"An item in {" ".join(words(name))} {failure.message}."
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


def target(form: type[Form], kind: str, key: str) -> tuple[Field, bool]:
	name, separator, rest = key.partition(".")
	if name not in form.fields:
		raise FormError(
			f"Form {form.__name__} has {kind} for '{key}', which is not a field"
		)
	if separator and rest != ITEMS:
		raise FormError(
			f"Form {form.__name__} has {kind} for '{key}', "
			f"which is neither '{name}' nor '{name}.{ITEMS}'"
		)

	field = form.fields[name]
	if separator and not field.is_list:
		raise FormError(
			f"Form {form.__name__} has {kind} for '{key}', but '{name}' is not a list"
		)
	return field, bool(separator)
