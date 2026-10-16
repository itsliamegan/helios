from enum import StrEnum
from typing import Any, cast

from luna.cli import HelpRequested, ParseError, Program, option
from luna.cli.parse import parse
from luna.test.assertion import assert_eq, assert_in, assert_raises, assert_that
from test.cli.support import terminal_width


class Mode(StrEnum):
	SAFE = "safe"
	FAST = "fast"


class Show(Program):
	name = "show"
	count: int = option(default=1, short="c", help="number of copies")
	verbose: bool = option(default=False, short="v")
	all: bool = option(default=False, short="a")
	binary: bool = option(default=False, short="b")

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


def declare_option(annotation: object, default: object) -> Any:
	def declare():
		type(
			"Declared",
			(Program,),
			{
				"__annotations__": {"value": annotation},
				"value": default,
				"name": "declared",
				"run": lambda self: None,
			},
		)

	return declare


def test_parses_value_kinds():
	class Kinds(Program):
		name = "kinds"
		specified: int = option(default=1)
		plain: int = 2
		required: int

		def run(self):
			pass

	assert_eq(
		parse(Kinds, ["--required", "3"]).values,
		{"specified": 1, "plain": 2, "required": 3},
	)
	assert_eq(
		parse(Kinds, ["--plain", "4", "--specified=5", "--required=6"]).values,
		{"specified": 5, "plain": 4, "required": 6},
	)
	assert_that(
		"the following arguments are required: --required"
		in parse_error(Kinds, []).message
	)


def test_parses_option_forms():
	for argv in [
		["--count", "2"],
		["--count=2"],
		["-c", "2"],
		["-c=2"],
		["-c2"],
		["--cou", "2"],
	]:
		assert_eq(parse(Show, argv).values["count"], 2)


def test_parses_flags():
	class Flags(Program):
		name = "flags"
		quiet: bool = option(default=False)
		loud: bool = False
		color: bool = option(default=True)

		def run(self):
			pass

	assert_eq(
		parse(Flags, []).values,
		{"quiet": False, "loud": False, "color": True},
	)
	assert_eq(
		parse(Flags, ["--quiet", "--loud"]).values,
		{"quiet": True, "loud": True, "color": True},
	)
	assert_in(
		"ignored explicit argument 'yes'",
		parse_error(Flags, ["--quiet=yes"]).message,
	)


def test_requires_declared_defaults_for_flags_and_lists():
	for annotation in [bool, list[str], list[Mode]]:
		for declared in [option(), option(short="q", help="help")]:
			assert_eq(
				declaration_error(declare_option(annotation, declared)),
				f"Declared.value: option requires a declared default: {annotation!r}",
			)

	def bare():
		class Bare(Program):
			name = "bare"
			quiet: bool

			def run(self):
				pass

	assert_eq(
		declaration_error(bare),
		"Bare.quiet: option requires a declared default: <class 'bool'>",
	)


def test_groups_short_flags():
	values = parse(Show, ["-vab"]).values

	assert_eq(
		[values["verbose"], values["all"], values["binary"]],
		[True, True, True],
	)


def test_rejects_unknown_options_and_bad_values():
	for argv, message in [
		(["--unknown"], "unrecognized arguments: --unknown"),
		(["--count", "two"], "invalid int value: 'two'"),
		(["--count"], "expected one argument"),
	]:
		error = parse_error(Show, argv)
		assert_in(message, error.message)
		assert_that(error.usage.startswith("usage: show"))


def test_parses_lists():
	class Lists(Program):
		name = "lists"
		tag: list[str] = option(default=["default"], short="t")
		numbers: list[int] = option(default=[])
		modes: list[Mode] = option(default=[])

		def run(self):
			pass

	assert_eq(
		parse(Lists, []).values,
		{"tag": ["default"], "numbers": [], "modes": []},
	)
	assert_eq(
		parse(
			Lists,
			["--tag", "one", "-t=two", "--numbers=3", "-tthree", "--modes=fast"],
		).values,
		{"tag": ["one", "two", "three"], "numbers": [3], "modes": [Mode.FAST]},
	)


def test_uses_a_new_list_default_for_each_parse():
	class Lists(Program):
		name = "lists"
		empty: list[str] = option(default=[])
		given: list[int] = option(default=[1])

		def run(self):
			pass

	first = parse(Lists, []).values
	cast(list[str], first["empty"]).append("changed")
	cast(list[int], first["given"]).append(2)
	second = parse(Lists, []).values

	assert_eq(second, {"empty": [], "given": [1]})


def test_parses_nullable_and_enum_options():
	class Values(Program):
		name = "values"
		limit: int | None = None
		mode: Mode = Mode.SAFE
		fallback: Mode | None = option(default=None)

		def run(self):
			pass

	assert_eq(
		parse(Values, []).values,
		{"limit": None, "mode": Mode.SAFE, "fallback": None},
	)
	assert_eq(
		parse(Values, ["--limit=3", "--mode=fast", "--fallback=safe"]).values,
		{"limit": 3, "mode": Mode.FAST, "fallback": Mode.SAFE},
	)
	assert_that(
		"argument --mode: invalid choice: 'slow' (choose from safe, fast)"
		in parse_error(Values, ["--mode", "slow"]).message
	)


def test_uses_names_verbatim():
	class Export(Program):
		name = "export"
		page_size: int = option(default=10, help="rows per page")

		def run(self):
			pass

	help = help_for(Export)

	assert_eq(parse(Export, ["--page_size", "20"]).values, {"page_size": 20})
	assert_in("[--page_size <page_size>]", help)
	assert_in("  --page_size <page_size>\n", help)
	assert_that(
		"unrecognized arguments: --page-size"
		in parse_error(Export, ["--page-size", "20"]).message
	)


def test_describes_options_in_help():
	class Choose(Program):
		name = "choose"
		count: int = option(default=1, short="c", help="number of copies")
		mode: Mode = option(default=Mode.SAFE, help="how to 100% run")
		modes: list[Mode] = option(default=[])

		def run(self):
			pass

	help = help_for(Choose)

	assert_in("  --count, -c <count>  number of copies\n", help)
	assert_in("  --mode <mode>        how to 100% run (choices: safe, fast)\n", help)
	assert_in("  --modes <modes>      choices: safe, fast\n", help)


def test_accepts_supported_types():
	class Supported(Program):
		name = "supported"
		text: str
		number: int
		mode: Mode
		maybe_text: str | None
		maybe_number: int | None
		maybe_mode: Mode | None
		flag: bool = False
		texts: list[str] = option(default=[])
		numbers: list[int] = option(default=[])
		modes: list[Mode] = option(default=[])

		def run(self):
			pass

	values = parse(
		Supported,
		[
			"--text=a",
			"--number=1",
			"--mode=fast",
			"--maybe_text=b",
			"--maybe_number=2",
			"--maybe_mode=safe",
			"--flag",
			"--texts=c",
			"--numbers=3",
			"--modes=safe",
		],
	).values

	assert_eq(
		values,
		{
			"text": "a",
			"number": 1,
			"mode": Mode.FAST,
			"maybe_text": "b",
			"maybe_number": 2,
			"maybe_mode": Mode.SAFE,
			"flag": True,
			"texts": ["c"],
			"numbers": [3],
			"modes": [Mode.SAFE],
		},
	)


def test_rejects_unsupported_types():
	for annotation in [
		float,
		bool | None,
		list[str] | None,
		list[float],
		list[list[str]],
		dict[str, str],
	]:
		assert_that(
			declaration_error(declare_option(annotation, option())).startswith(
				"Declared.value: unsupported option type:"
			)
		)
	assert_eq(
		declaration_error(declare_option(str | int, option())),
		"Declared.value: unsupported type: str | int",
	)


def test_rejects_mismatched_defaults():
	assert_eq(
		declaration_error(declare_option(int, None)),
		"Declared.value: default None requires a nullable type: <class 'int'>",
	)
	for annotation, default in [
		(int, True),
		(int, "1"),
		(str, 1),
		(bool, 0),
		(Mode, "safe"),
		(list[int], [True]),
		(list[str], ("a",)),
		(int | None, "1"),
	]:
		for declared in [default, option(default=default)]:
			assert_that(
				declaration_error(declare_option(annotation, declared)).startswith(
					f"Declared.value: default {default!r} does not match type"
				)
			)


def test_validates_short_aliases():
	def declare(shorts: dict[str, str]) -> Any:
		def create():
			type(
				"Aliases",
				(Program,),
				{
					"__annotations__": dict.fromkeys(shorts, bool),
					**{
						name: option(default=False, short=short)
						for name, short in shorts.items()
					},
					"name": "aliases",
					"run": lambda self: None,
				},
			)

		return create

	assert_eq(
		declaration_error(declare({"verbose": "v", "version": "v"})),
		"Aliases.version: duplicate short alias: 'v'",
	)
	assert_eq(
		declaration_error(declare({"hidden": "h"})),
		"Aliases.hidden: short alias is reserved: 'h'",
	)
	for short in ["vv", "1", "é", ""]:
		assert_eq(
			declaration_error(declare({"verbose": short})),
			f"Aliases.verbose: short alias must be a single ASCII letter: {short!r}",
		)
