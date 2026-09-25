from annotationlib import Format, ForwardRef, get_annotations
from collections.abc import Collection
from dataclasses import dataclass
from types import NoneType
from typing import Any, ClassVar, Union, get_args, get_origin

MISSING: Any = object()


class DeclarationError(Exception):
	def __init__(self, name: str, detail: str):
		super().__init__(f"{name}: {detail}")
		self.name = name
		self.detail = detail


@dataclass
class Declared:
	owner: type
	name: str
	annotation: Any
	default: object


def declared(owner: type) -> list[Declared]:
	entries = []
	for name, annotation in get_annotations(owner, format=Format.FORWARDREF).items():
		if annotation is ClassVar or get_origin(annotation) is ClassVar:
			continue
		if isinstance(annotation, str):
			raise DeclarationError(
				name,
				f"string annotations are not supported: {annotation!r}",
			)
		reference = forward_reference(annotation)
		if reference is not None:
			raise DeclarationError(
				name,
				f"unresolved annotation: {reference.__forward_arg__}",
			)
		entries.append(
			Declared(owner, name, annotation, vars(owner).get(name, MISSING))
		)
	return entries


def forward_reference(annotation: Any) -> ForwardRef | None:
	if isinstance(annotation, ForwardRef):
		return annotation
	for argument in get_args(annotation):
		reference = forward_reference(argument)
		if reference is not None:
			return reference
	return None


def split_nullable(name: str, annotation: Any) -> tuple[Any, bool]:
	if get_origin(annotation) is not Union:
		return annotation, False

	members = get_args(annotation)
	if len(members) != 2:
		raise DeclarationError(name, f"unsupported type: {annotation!r}")
	value_index = 1 if members[0] is NoneType else 0
	if members[1 - value_index] is not NoneType:
		raise DeclarationError(name, f"unsupported type: {annotation!r}")
	return members[value_index], True


def check_keywords(
	owner: type,
	noun: str,
	given: Collection[str],
	accepted: Collection[str],
	required: Collection[str],
):
	unexpected = [name for name in given if name not in accepted]
	if unexpected:
		raise TypeError(
			f"{owner.__name__} got unexpected {noun}: {", ".join(unexpected)}"
		)

	missing = [name for name in required if name not in given]
	if missing:
		raise TypeError(f"{owner.__name__} is missing {noun}: {", ".join(missing)}")
