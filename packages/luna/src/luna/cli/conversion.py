from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, get_args, get_origin

from luna.declarative import Declaration, DeclarationError, MISSING


@dataclass
class Conversion:
	type: Any
	nullable: bool


def scalar(annotation: object) -> bool:
	return (
		annotation is str
		or annotation is int
		or annotation is Path
		or choices(annotation)
	)


def choices(annotation: object) -> bool:
	return isinstance(annotation, type) and issubclass(annotation, StrEnum)


def check_default(
	declaration: Declaration,
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
			matches_scalar(item_type, item) for item in default
		)
	else:
		return matches_scalar(annotation, default)


def matches_scalar(annotation: Any, default: object) -> bool:
	if annotation is Path:
		# Path() returns an instance of a subclass for the current platform,
		# such as PosixPath, so a Path default's type is never Path itself.
		return isinstance(default, Path)
	else:
		return type(default) is annotation
