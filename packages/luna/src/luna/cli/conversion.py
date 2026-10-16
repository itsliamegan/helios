from dataclasses import dataclass
from enum import StrEnum
from typing import Any, get_args, get_origin

from luna.declarative import Declaration, DeclarationError, MISSING


@dataclass
class Conversion:
	type: Any
	nullable: bool


def scalar(annotation: object) -> bool:
	return annotation is str or annotation is int or choices(annotation)


def choices(annotation: object) -> bool:
	return isinstance(annotation, type) and issubclass(annotation, StrEnum)


def check_default(
	declaration: Declaration[Conversion],
	conversion: Conversion,
	default: object,
):
	if default is MISSING:
		return
	elif default is None:
		if not conversion.nullable:
			raise DeclarationError(
				declaration.name,
				f"default None requires a nullable type: {declaration.annotation!r}",
			)
	elif not matches(conversion.type, default):
		raise DeclarationError(
			declaration.name,
			f"default {default!r} does not match type {declaration.annotation!r}",
		)


def matches(annotation: Any, default: object) -> bool:
	if get_origin(annotation) is list:
		(item_type,) = get_args(annotation)
		return type(default) is list and all(
			type(item) is item_type for item in default
		)
	else:
		return type(default) is annotation
