from annotationlib import Format, ForwardRef, get_annotations
from collections.abc import Collection, Mapping
from functools import reduce
from operator import or_
from types import NoneType
from typing import ClassVar, Protocol, Union, get_args, get_origin

MISSING: object = object()


class DeclarationError(Exception):
	def __init__(self, name: str, detail: str):
		super().__init__(f"{name}: {detail}")
		self.name = name
		self.detail = detail


class Namespace(Protocol):
	def find(self, name: str) -> type | None: ...


class Declaration:
	def __init__(
		self,
		owner: type,
		name: str,
		annotation: object,
		default: object,
		error: type[Exception],
	):
		self.owner = owner
		self.name = name
		self.annotation = annotation
		self.default = default
		self.error = error
		self.fallback: Namespace | None = None

	@property
	def pending(self) -> bool:
		return forward_reference(self.annotation) is not None

	def resolve(self) -> object:
		if self.pending:
			try:
				self.annotation = self.evaluate()
			except DeclarationError as error:
				raise self.reject(error) from error
		return self.annotation

	def evaluate(self) -> object:
		supplied: dict[str, type] = {}
		while True:
			try:
				return evaluate_annotation(self.annotation, self.owner, supplied)
			except NameError as error:
				missing = error.name
				if missing is None or missing in supplied:
					raise self.unresolved(missing) from error
				supplied[missing] = self.lookup(missing)

	def lookup(self, missing: str) -> type:
		found = None if self.fallback is None else self.fallback.find(missing)
		if found is None:
			raise self.unresolved(missing)
		return found

	def unresolved(self, missing: str | None) -> DeclarationError:
		return DeclarationError(self.name, f"unresolved annotation: {missing}")

	def reject(self, error: DeclarationError) -> Exception:
		return self.error(f"{self.owner.__name__}.{error}")


def declarations(owner: type, error: type[Exception]) -> list[Declaration]:
	found = []
	for name, annotation in get_annotations(owner, format=Format.FORWARDREF).items():
		if annotation is ClassVar or get_origin(annotation) is ClassVar:
			continue
		if isinstance(annotation, str):
			raise error(
				f"{owner.__name__}.{name}: "
				f"string annotations are not supported: {annotation!r}"
			)

		default = vars(owner).get(name, MISSING)
		found.append(Declaration(owner, name, annotation, default, error))
	return found


def evaluate_annotation(
	annotation: object,
	owner: type,
	supplied: Mapping[str, type],
) -> object:
	if isinstance(annotation, ForwardRef):
		return annotation.evaluate(locals={**vars(owner), **supplied})
	origin = get_origin(annotation)
	if origin is None or forward_reference(annotation) is None:
		return annotation

	evaluated = tuple(
		evaluate_annotation(argument, owner, supplied)
		for argument in get_args(annotation)
	)
	if origin is Union:
		return reduce(or_, evaluated)
	return origin[evaluated]


def forward_reference(annotation: object) -> ForwardRef | None:
	if isinstance(annotation, ForwardRef):
		return annotation

	for argument in get_args(annotation):
		reference = forward_reference(argument)
		if reference is not None:
			return reference
	return None


def split_nullable(name: str, annotation: object) -> tuple[object, bool]:
	if get_origin(annotation) is not Union:
		return annotation, False

	members = get_args(annotation)
	if len(members) != 2:
		raise DeclarationError(name, f"unsupported type: {annotation!r}")

	value_index = 1 if members[0] is NoneType else 0
	if members[1 - value_index] is not NoneType:
		raise DeclarationError(name, f"unsupported type: {annotation!r}")
	return members[value_index], True


def check_init_keywords(
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


def check_single_base(owner: type, base: type, error: type[Exception]):
	if owner.__bases__ != (base,):
		raise error(f"{owner.__name__} must inherit only from {base.__name__}")
