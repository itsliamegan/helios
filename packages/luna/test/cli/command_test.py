from enum import StrEnum
from typing import Any

from luna.cli import Command, argument, option
from luna.test.assertion import assert_eq, assert_raises


class Apply(Command):
	name = "apply"
	target: str = argument(default="latest")
	dry: bool = option(default=False, short="d")
	steps: list[int] = option(default=[])

	def run(self) -> object:
		return ("apply", self.target, self.dry, self.steps)


def declaration_error(declare: Any) -> str:
	with assert_raises(ValueError) as raised:
		declare()
	return str(raised.exception)


def test_constructs_without_argv():
	apply = Apply(target="v2", dry=True, steps=[3])

	assert_eq(apply.run(), ("apply", "v2", True, [3]))


def test_applies_defaults_when_constructed():
	apply = Apply()

	assert_eq(apply.run(), ("apply", "latest", False, []))


def test_copies_defaults_for_each_instance():
	first = Apply()
	first.steps.append(1)

	assert_eq(Apply().steps, [])


def test_rejects_unexpected_and_missing_values():
	class Greet(Command):
		name = "greet"
		person: str = argument()

		def run(self):
			pass

	with assert_raises(TypeError) as missing:
		Greet()  # ty: ignore[missing-argument]
	with assert_raises(TypeError) as unexpected:
		Greet(person="Ada", loud=True)  # ty: ignore[unknown-argument]

	assert_eq(str(missing.exception), "Greet is missing values: person")
	assert_eq(str(unexpected.exception), "Greet got unexpected values: loud")


def test_requires_run():
	class Idle(Command):
		name = "idle"

	with assert_raises(TypeError):
		Idle()


def test_validates_names():
	def missing():
		class Unnamed(Command):
			pass

	def empty():
		class Unnamed(Command):
			name = ""

	def not_a_string():
		class Unnamed(Command):
			name = 1

	def dashed():
		class Unnamed(Command):
			name = "-apply"

	for declare in [missing, empty, not_a_string]:
		assert_eq(
			declaration_error(declare),
			"Unnamed must set name to a nonempty string",
		)
	assert_eq(
		declaration_error(dashed),
		"Unnamed.name must not begin with '-': '-apply'",
	)


def test_rejects_reserved_names():
	def named(value: str, annotation: object = bool) -> Any:
		def declare():
			type(
				"Reserved",
				(Command,),
				{"__annotations__": {value: annotation}, "name": "reserved"},
			)

		return declare

	for value in [
		"run",
		"main",
		"name",
		"commands",
		"help",
		"declare",
		"declared",
		"settled",
		"__init__",
	]:
		assert_eq(
			declaration_error(named(value)),
			f"Reserved.{value}: name is reserved",
		)


def test_rejects_reserved_names_with_pending_annotations():
	def declare():
		class Reserved(Command):
			name = "reserved"
			run: Pending  # noqa: F821  # ty: ignore[unresolved-reference]

	assert_eq(declaration_error(declare), "Reserved.run: name is reserved")


def test_requires_direct_inheritance():
	class Status(Command):
		name = "status"

		def run(self):
			pass

	class Mixin:
		pass

	def from_command():
		class Extended(Status):
			name = "extended"

	def with_mixin():
		class Extended(Command, Mixin):
			name = "extended"

	def mixin_first():
		class Extended(Mixin, Command):
			name = "extended"

	for declare in [from_command, with_mixin, mixin_first]:
		assert_eq(
			declaration_error(declare),
			"Extended must inherit only from Command",
		)


def test_resolves_forward_references_before_use():
	class Later(Command):
		name = "later"
		mode: Pending = option(help="a mode declared later")

		def run(self):
			return self.mode

	class Pending(StrEnum):
		ON = "on"

	assert_eq(Later(mode=Pending.ON).run(), Pending.ON)


def test_rejects_forward_references_that_never_resolve():
	class Later(Command):
		name = "later"
		mode: Missing = option()  # noqa: F821  # ty: ignore[unresolved-reference]

		def run(self):
			pass

	with assert_raises(ValueError) as raised:
		Later(mode="on")

	assert_eq(str(raised.exception), "Later.mode: unresolved annotation: Missing")
