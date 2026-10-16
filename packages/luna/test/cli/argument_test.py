from enum import StrEnum
from typing import Any

from luna.cli import HelpRequested, ParseError, Program, argument
from luna.cli.parse import parse
from luna.test.assertion import assert_eq, assert_in, assert_raises, assert_that
from test.cli.support import terminal_width


class Mode(StrEnum):
	SAFE = "safe"
	FAST = "fast"


class Copy(Program):
	name = "copy"
	source: str = argument(help="file to copy")
	count: int = argument()
	mode: Mode = argument(default=Mode.SAFE)
	destination: str | None = argument(default=None)

	def run(self):
		pass


def declaration_error(declare: Any) -> str:
	with assert_raises(ValueError) as raised:
		declare()
	return str(raised.exception)


def parse_error(program: type[Program], argv: list[str]) -> ParseError:
	with assert_raises(ParseError) as raised:
		parse(program, argv)
	return raised.exception


def help_for(program: type[Program]) -> str:
	with terminal_width(80), assert_raises(HelpRequested) as raised:
		parse(program, ["--help"])
	return raised.exception.help


def declare_argument(annotation: object, specifier: object) -> Any:
	def declare():
		type(
			"Declared",
			(Program,),
			{
				"__annotations__": {"value": annotation},
				"value": specifier,
				"name": "declared",
				"run": lambda self: None,
			},
		)

	return declare


def test_parses_arguments_in_order():
	values = parse(Copy, ["input.txt", "2", "fast", "output.txt"]).values

	assert_eq(
		values,
		{
			"source": "input.txt",
			"count": 2,
			"mode": Mode.FAST,
			"destination": "output.txt",
		},
	)


def test_applies_defaults_to_omitted_optional_arguments():
	values = parse(Copy, ["input.txt", "2"]).values

	assert_eq(
		values,
		{"source": "input.txt", "count": 2, "mode": Mode.SAFE, "destination": None},
	)


def test_rejects_missing_and_extra_arguments():
	for argv in [[], ["input.txt"], ["input.txt", "2", "fast", "output.txt", "extra"]]:
		error = parse_error(Copy, argv)
		assert_that(error.usage.startswith("usage: copy"))


def test_rejects_invalid_values():
	count_error = parse_error(Copy, ["input.txt", "two"])
	mode_error = parse_error(Copy, ["input.txt", "2", "slow"])

	assert_in("invalid int value: 'two'", count_error.message)
	assert_in("invalid choice: 'slow' (choose from safe, fast)", mode_error.message)


def test_uses_name_as_placeholder():
	class Export(Program):
		name = "export"
		output_path: str = argument(help="where to write")

		def run(self):
			pass

	help = help_for(Export)

	assert_that(help.startswith("usage: export [--help] <output_path>\n"))
	assert_in("  <output_path>  where to write\n", help)
	assert_eq(parse(Export, ["out.txt"]).values, {"output_path": "out.txt"})


def test_lists_enum_choices_in_help():
	help = help_for(Copy)

	assert_in("  <mode>         choices: safe, fast\n", help)


def test_accepts_supported_types():
	class Supported(Program):
		name = "supported"
		text: str = argument()
		number: int = argument()
		mode: Mode = argument()
		maybe_text: str | None = argument(default=None)
		maybe_number: int | None = argument(default=None)
		maybe_mode: Mode | None = argument(default=None)

		def run(self):
			pass

	assert_eq(
		parse(Supported, ["a", "1", "fast", "b", "2", "safe"]).values,
		{
			"text": "a",
			"number": 1,
			"mode": Mode.FAST,
			"maybe_text": "b",
			"maybe_number": 2,
			"maybe_mode": Mode.SAFE,
		},
	)


def test_rejects_unsupported_types():
	for annotation in [float, bool, list[str], bool | None, list[str] | None]:
		assert_that(
			declaration_error(declare_argument(annotation, argument())).startswith(
				"Declared.value: unsupported argument type:"
			)
		)
	assert_eq(
		declaration_error(declare_argument(str | int, argument())),
		"Declared.value: unsupported type: str | int",
	)


def test_rejects_mismatched_defaults():
	assert_eq(
		declaration_error(declare_argument(int, argument(default=None))),
		"Declared.value: default None requires a nullable type: <class 'int'>",
	)
	for annotation, default in [
		(int, True),
		(int, "1"),
		(str, 1),
		(Mode, "safe"),
		(int | None, "1"),
	]:
		assert_that(
			declaration_error(
				declare_argument(annotation, argument(default=default))
			).startswith(f"Declared.value: default {default!r} does not match type")
		)


def test_requires_required_arguments_first():
	def declare():
		class Order(Program):
			name = "order"
			first: str = argument(default="x")
			second: str = argument()

			def run(self):
				pass

	assert_eq(
		declaration_error(declare),
		"Order.second: required argument follows optional argument first",
	)
