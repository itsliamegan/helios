from abc import ABC, abstractmethod
from annotationlib import Format, get_annotations
import inspect
import string
from typing import Any, ClassVar, dataclass_transform, get_origin

from luna.cli.argument import Argument, argument
from luna.cli.conversion import Conversion
from luna.cli.option import Option, option
from luna.declarative import Declaration, check_init_keywords, declarations

RESERVED_NAMES = {"run", "main", "name", "commands", "help"}
RESERVED_SHORTS = {"h"}


@dataclass_transform(
	kw_only_default=True,
	eq_default=False,
	field_specifiers=(argument, option),
)
class Runnable(ABC):
	name: ClassVar[str]
	declared: ClassVar[dict[str, Argument | Option]] = {}

	def __init__(self, **values: Any):
		owner = type(self)
		settled = owner.settled()
		check_init_keywords(
			owner,
			"values",
			values,
			settled,
			[name for name, value in settled.items() if value.required],
		)
		for name, value in settled.items():
			setattr(self, name, values.get(name, value.initial))

	@classmethod
	def declare(cls):
		check_name(cls)
		check_reserved(cls)

		declared = {}
		for declaration in declarations(cls, settle, ValueError):
			value = declared_value(declaration.default)
			value.bind(declaration)
			declared[declaration.name] = value

		check_arguments(cls, declared)
		check_shorts(cls, declared)
		for name, value in declared.items():
			setattr(cls, name, value)
		cls.declared = declared

	@classmethod
	def settled(cls) -> dict[str, Argument | Option]:
		for value in cls.declared.values():
			value.declaration.resolve()
		return cls.declared

	@abstractmethod
	def run(self) -> object: ...


def declared_value(default: object) -> Argument | Option:
	if isinstance(default, Argument | Option):
		return default
	else:
		return Option(default)


def settle(declaration: Declaration[Conversion]) -> Conversion:
	return declared_value(declaration.default).settle(declaration)


def description(owner: type) -> str | None:
	docstring = vars(owner).get("__doc__")
	if docstring is None:
		return None

	return inspect.cleandoc(docstring)


def check_name(owner: type):
	name = vars(owner).get("name")
	if not isinstance(name, str) or not name:
		raise ValueError(f"{owner.__name__} must set name to a nonempty string")
	if name.startswith("-"):
		raise ValueError(f"{owner.__name__}.name must not begin with '-': {name!r}")


def check_reserved(owner: type):
	reserved = set(RESERVED_NAMES)
	for base in owner.__mro__[1:]:
		reserved.update(vars(base))

	annotations = get_annotations(owner, format=Format.FORWARDREF)
	for name, annotation in annotations.items():
		if annotation is ClassVar or get_origin(annotation) is ClassVar:
			continue
		if name in reserved:
			raise ValueError(f"{owner.__name__}.{name}: name is reserved")


def check_arguments(owner: type, declared: dict[str, Argument | Option]):
	optional = None
	for name, value in declared.items():
		if not isinstance(value, Argument):
			continue
		if not value.required:
			optional = name
		elif optional is not None:
			raise ValueError(
				f"{owner.__name__}.{name}: required argument follows "
				f"optional argument {optional}"
			)


def check_shorts(owner: type, declared: dict[str, Argument | Option]):
	shorts = set()
	for name, value in declared.items():
		if not isinstance(value, Option) or value.short is None:
			continue

		short = value.short
		if len(short) != 1 or short not in string.ascii_letters:
			raise ValueError(
				f"{owner.__name__}.{name}: short alias must be a single "
				f"ASCII letter: {short!r}"
			)
		if short in RESERVED_SHORTS:
			raise ValueError(
				f"{owner.__name__}.{name}: short alias is reserved: {short!r}"
			)
		if short in shorts:
			raise ValueError(
				f"{owner.__name__}.{name}: duplicate short alias: {short!r}"
			)
		shorts.add(short)
