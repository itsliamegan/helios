from annotationlib import Format, ForwardRef, get_annotations
from collections.abc import Callable, Collection
from types import NoneType
from typing import ClassVar, Union, get_args, get_origin

MISSING: object = object()


class DeclarationError(Exception):
	def __init__(self, name: str, detail: str):
		super().__init__(f"{name}: {detail}")
		self.name = name
		self.detail = detail


class Declaration[T]:
	value: T

	def __init__(
		self,
		owner: type,
		name: str,
		annotation: object,
		default: object,
		settle: Callable[[Declaration[T]], T],
		error: type[Exception],
	):
		self.owner = owner
		self.name = name
		self.annotation = annotation
		self.default = default
		self.settle = settle
		self.error = error
		self.settled = False
		if not self.pending:
			self.resolve()

	@property
	def pending(self) -> bool:
		return forward_reference(self.annotation) is not None

	def resolve(self) -> T:
		if not self.settled:
			try:
				if self.pending:
					self.annotation = self.evaluate()
				self.value = self.settle(self)
			except DeclarationError as error:
				raise self.error(f"{self.owner.__name__}.{error}") from error
			self.settled = True
		return self.value

	def evaluate(self) -> object:
		try:
			return get_annotations(self.owner)[self.name]
		except NameError as error:
			raise DeclarationError(
				self.name,
				f"unresolved annotation: {error.name}",
			) from error


def declarations[T](
	owner: type,
	settle: Callable[[Declaration[T]], T],
	error: type[Exception],
) -> list[Declaration[T]]:
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
		found.append(Declaration(owner, name, annotation, default, settle, error))
	return found


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
