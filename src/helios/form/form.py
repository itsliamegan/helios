from annotationlib import get_annotations
from copy import copy
from dataclasses import dataclass, replace
from types import NoneType
from typing import (
	Any,
	ClassVar,
	Self,
	Union,
	dataclass_transform,
	get_args,
	get_origin,
)

from helios.http import Input

from .errors import Errors
from .parser import Parser, RawValue, is_verbatim, resolve
from .rule import Required, Rule, RuleError

MISSING: Any = object()


class Failure(ValueError):
	def __init__(self, rule: str, message: str):
		super().__init__(message)
		self.rule = rule
		self.message = message


@dataclass
class Field:
	name: str
	parser: Parser[Any]
	default: object
	verbatim: bool
	extra_rules: list[Rule[Any, Any]]

	@property
	def required(self) -> bool:
		return self.default is MISSING

	@property
	def initial(self) -> object:
		return copy(self.default)

	@property
	def rules(self) -> list[Rule[Any, Any]]:
		if self.required:
			return [Required(), self.parser, *self.extra_rules]
		else:
			return [self.parser, *self.extra_rules]

	def raw(self, input: Input) -> RawValue | None:
		if self.name not in input:
			return None

		value = input[self.name]
		if self.verbatim:
			return value
		else:
			return trim(value)

	def validate(self, input: Input) -> object:
		value = self.raw(input)
		if value is None and not self.required:
			return self.initial

		for rule in self.rules:
			try:
				value = rule.check(value)
			except RuleError as error:
				raise Failure(rule.name, error.message or rule.message) from error
		return value

	def __get__(self, form: Form | None, owner: type) -> Any:
		if form is None:
			return self

		try:
			return form.values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def __set__(self, form: Form, value: object):
		form.values[self.name] = value


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

		for name, annotation in get_annotations(cls, eval_str=True).items():
			if annotation is ClassVar or get_origin(annotation) is ClassVar:
				continue

			if name in RESERVED:
				raise TypeError(
					f"Form {cls.__name__} has a field named '{name}', which Form uses"
				)
			try:
				field = declare(
					name,
					annotation,
					vars(cls).get(name, MISSING),
					cls.rules.get(name, []),
				)
			except TypeError as error:
				raise TypeError(f"{cls.__name__}.{name}: {error}") from error
			setattr(cls, name, field)
			fields[name] = field

		for name in cls.rules:
			if name not in fields:
				raise TypeError(
					f"Form {cls.__name__} has rules for '{name}', which is not a field"
				)
		cls.fields = fields

	def __init__(self, **values: Any):
		form = type(self)

		extra = [name for name in values if name not in form.fields]
		if extra:
			raise TypeError(
				f"{form.__name__} got unexpected fields: {", ".join(extra)}"
			)

		missing = [
			name
			for name, field in form.fields.items()
			if field.required and name not in values
		]
		if missing:
			raise TypeError(f"{form.__name__} is missing fields: {", ".join(missing)}")

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
			return f"{readable(name)} {failure.message}."

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={self.values[name]!r}"
			for name in type(self).fields
			if name in self.values
		)
		return f"{type(self).__name__}({values})"


RESERVED = {"values", *vars(Form)}


def declare(
	name: str,
	annotation: Any,
	default: object,
	rules: list[Rule[Any, Any]],
) -> Field:
	annotation = unwrap_nullable(annotation)
	return Field(
		name,
		resolve(annotation),
		default,
		is_verbatim(annotation),
		rules,
	)


def unwrap_nullable(annotation: Any) -> Any:
	if get_origin(annotation) is not Union:
		return annotation

	members = [member for member in get_args(annotation) if member is not NoneType]
	if len(members) != 1 or len(get_args(annotation)) != 2:
		raise TypeError(f"unsupported field type: {annotation!r}")
	return members[0]


def trim(value: RawValue) -> RawValue | None:
	if isinstance(value, str):
		return value.strip() or None
	else:
		items = [item.strip() for item in value]
		return [item for item in items if item] or None


def readable(name: str) -> str:
	words = name.replace("_", " ")
	return words[:1].upper() + words[1:]
