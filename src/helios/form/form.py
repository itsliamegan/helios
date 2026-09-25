from annotationlib import get_annotations
import copy
from dataclasses import dataclass
from types import NoneType
from typing import (
	Any,
	ClassVar,
	NewType,
	Self,
	Union,
	dataclass_transform,
	get_args,
	get_origin,
)
import uuid

from helios import http
from helios.http import Input

from . import parser
from .errors import Errors
from .parser import ParseError, Parser, RawValue

Verbatim = NewType("Verbatim", str)

MISSING: Any = object()

SCALARS: dict[Any, Parser[Any]] = {
	str: parser.Str(),
	Verbatim: parser.Str(),
	bool: parser.Bool(),
	int: parser.Int(),
	uuid.UUID: parser.UUID(),
	http.URL: parser.URL(),
}


@dataclass
class Field:
	name: str
	parser: Parser[Any]
	default: object
	verbatim: bool

	@property
	def required(self) -> bool:
		return self.default is MISSING

	def initial(self) -> object:
		return copy.copy(self.default)

	def raw(self, input: Input) -> RawValue | None:
		if self.name not in input:
			return None
		value = input[self.name]
		if self.verbatim:
			return value
		return trim(value)

	def validate(self, input: Input) -> object:
		raw = self.raw(input)
		if raw is None:
			if self.required:
				raise ParseError("required", "must be provided")
			return self.initial()
		return self.parser.parse(raw)

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

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		fields = dict(cls.fields)
		for name, annotation in get_annotations(cls, eval_str=True).items():
			if annotation is ClassVar or get_origin(annotation) is ClassVar:
				continue
			if name in RESERVED:
				raise TypeError(
					f'{cls.__name__} has a field named "{name}", which Form uses'
				)
			try:
				field = declare(name, annotation, vars(cls).get(name, MISSING))
			except TypeError as error:
				raise TypeError(f"{cls.__name__}.{name}: {error}") from error
			setattr(cls, name, field)
			fields[name] = field
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
			self.values[name] = values[name] if name in values else field.initial()

	@classmethod
	def validate(cls, input: Input) -> tuple[Self, Errors]:
		form = cls.__new__(cls)
		form.values = {}
		errors = Errors()
		for name, field in cls.fields.items():
			try:
				form.values[name] = field.validate(input)
			except ParseError as error:
				errors.add(name, f"{readable(name)} {error}.")
		return form, errors

	def __repr__(self) -> str:
		values = ", ".join(
			f"{name}={self.values[name]!r}"
			for name in type(self).fields
			if name in self.values
		)
		return f"{type(self).__name__}({values})"


RESERVED = {"values", *vars(Form)}


def declare(name: str, annotation: Any, default: object) -> Field:
	annotation = unwrap_nullable(annotation)
	if get_origin(annotation) is list:
		(item,) = get_args(annotation)
		return Field(name, parser.List(scalar(item)), default, item is Verbatim)
	return Field(name, scalar(annotation), default, annotation is Verbatim)


def unwrap_nullable(annotation: Any) -> Any:
	if get_origin(annotation) is not Union:
		return annotation
	members = [member for member in get_args(annotation) if member is not NoneType]
	if len(members) != 1 or len(get_args(annotation)) != 2:
		raise TypeError(f"unsupported field type: {annotation!r}")
	return members[0]


def scalar(annotation: Any) -> Parser[Any]:
	try:
		return SCALARS[annotation]
	except KeyError, TypeError:
		raise TypeError(f"unsupported field type: {annotation!r}") from None


def trim(value: RawValue) -> RawValue | None:
	if isinstance(value, str):
		return value.strip() or None
	items = [item.strip() for item in value]
	return [item for item in items if item] or None


def readable(name: str) -> str:
	words = name.replace("_", " ")
	return words[:1].upper() + words[1:]
