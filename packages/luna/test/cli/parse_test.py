from contextlib import redirect_stderr, redirect_stdout
from enum import StrEnum
from io import StringIO

from luna.cli import Command, HelpRequested, ParseError, Program, argument, option
from luna.cli.parse import CommandMissing, parse
from luna.test.assertion import assert_eq, assert_raises
from test.cli.support import terminal_width


class Mode(StrEnum):
	SAFE = "safe"
	FAST = "fast"


class Copy(Program):
	"""Copy a file."""

	name = "copy"
	source: str = argument(help="file to copy")
	destination: str | None = argument(default=None, help="where to copy it")
	count: int = option(default=1, short="c", help="number of copies")
	mode: Mode = Mode.SAFE
	verbose: bool = option(default=False, short="v")
	tag: list[str] = option(default=["default"], short="t")

	def run(self):
		pass


class Move(Command):
	name = "move"
	source: str = argument()

	def run(self):
		pass


class Files(Program):
	name = "files"
	commands = (Move,)


def test_parses_arguments_and_options_together():
	result = parse(
		Copy,
		[
			"input.txt",
			"--count",
			"2",
			"-v",
			"output.txt",
			"--mode=fast",
			"-t",
			"one",
			"--tag=two",
		],
	)

	assert_eq(
		result.values,
		{
			"source": "input.txt",
			"destination": "output.txt",
			"count": 2,
			"mode": Mode.FAST,
			"verbose": True,
			"tag": ["one", "two"],
		},
	)


def test_applies_defaults_when_omitted():
	assert_eq(
		parse(Copy, ["input.txt"]).values,
		{
			"source": "input.txt",
			"destination": None,
			"count": 1,
			"mode": Mode.SAFE,
			"verbose": False,
			"tag": ["default"],
		},
	)


def test_ends_option_parsing_at_terminator():
	values = parse(Copy, ["-c", "-2", "--", "-input", "--count"]).values

	assert_eq(values["count"], -2)
	assert_eq(values["source"], "-input")
	assert_eq(values["destination"], "--count")


def test_returns_help_message():
	with terminal_width(80), assert_raises(HelpRequested) as raised:
		parse(Copy, ["--help"])

	assert_eq(
		raised.exception.help,
		"usage: copy [--help] [--count <count>] [--mode <mode>] [--verbose]\n"
		"            [--tag <tag>]\n"
		"            <source> [<destination>]\n"
		"\n"
		"Copy a file.\n"
		"\n"
		"arguments:\n"
		"  <source>             file to copy\n"
		"  <destination>        where to copy it\n"
		"\n"
		"options:\n"
		"  --help, -h           show this help message and exit\n"
		"  --count, -c <count>  number of copies\n"
		"  --mode <mode>        choices: safe, fast\n"
		"  --verbose, -v\n"
		"  --tag, -t <tag>\n",
	)


def test_doesnt_write_output():
	stdout = StringIO()
	stderr = StringIO()

	with redirect_stdout(stdout), redirect_stderr(stderr):
		for program, argv in [(Copy, []), (Files, ["move"])]:
			with assert_raises(ParseError):
				parse(program, argv)
		with assert_raises(CommandMissing):
			parse(Files, [])
		for program, argv in [
			(Copy, ["--help"]),
			(Files, ["--help"]),
			(Files, ["move", "--help"]),
		]:
			with assert_raises(HelpRequested):
				parse(program, argv)

	assert_eq(stdout.getvalue(), "")
	assert_eq(stderr.getvalue(), "")
