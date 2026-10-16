import argparse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Never, TYPE_CHECKING

from luna.cli.argument import Argument
from luna.cli.conversion import choices
from luna.cli.option import Option
from luna.cli.runnable import Runnable, description

if TYPE_CHECKING:
	from luna.cli.command import Command
	from luna.cli.program import Program

COMMAND_DESTINATION = "__command"


@dataclass
class ParseResult:
	program: type[Program]
	command: type[Command] | None
	values: dict[str, object]


class ParseError(Exception):
	def __init__(self, message: str, usage: str):
		super().__init__(message)
		self.message = message
		self.usage = usage


class HelpRequested(Exception):
	def __init__(self, help: str):
		super().__init__(help)
		self.help = help


class CommandMissing(Exception):
	def __init__(self, help: str):
		super().__init__(help)
		self.help = help


class ArgumentParser(argparse.ArgumentParser):
	def error(self, message: str) -> Never:
		raise ParseError(message, self.format_usage())


class CommandParser(ArgumentParser):
	# argparse parses commands with parse_known_args and reports leftover
	# arguments from the program's parser, which prints the program's usage.
	def parse_known_args(
		self,
		args: Iterable[str] | None = None,
		namespace: Any = None,
	) -> tuple[Any, list[str]]:
		namespace, extras = super().parse_known_args(args, namespace)
		if extras:
			self.error(f"unrecognized arguments: {" ".join(extras)}")
		return namespace, extras


class HelpAction(argparse.Action):
	def __init__(
		self,
		option_strings: list[str],
		dest: str = argparse.SUPPRESS,
		default: object = argparse.SUPPRESS,
		help: str | None = None,
	):
		super().__init__(
			option_strings=option_strings,
			dest=dest,
			nargs=0,
			default=default,
			help=help,
		)

	def __call__(
		self,
		parser: argparse.ArgumentParser,
		namespace: argparse.Namespace,
		values: object,
		option_string: str | None = None,
	):
		raise HelpRequested(parser.format_help())


def parse(program: type[Program], argv: list[str]) -> ParseResult:
	if program.commands:
		return parse_commands(program, argv)
	else:
		return parse_program(program, argv)


def create_parser(runnable: type[Runnable]) -> ArgumentParser:
	parser = ArgumentParser(
		prog=runnable.name,
		description=description(runnable),
		formatter_class=argparse.RawDescriptionHelpFormatter,
		add_help=False,
		color=False,
	)
	add_help(parser)
	return parser


def add_commands(parser: ArgumentParser, commands: tuple[type[Command], ...]):
	subparsers = parser.add_subparsers(
		dest=COMMAND_DESTINATION,
		required=True,
		parser_class=CommandParser,
		metavar="<command>",
	)
	for command in commands:
		command_parser = subparsers.add_parser(
			command.name,
			description=description(command),
			help=escape(description(command)),
			formatter_class=argparse.RawDescriptionHelpFormatter,
			add_help=False,
		)
		add_help(command_parser)
		add_values(command_parser, command)


def add_help(parser: argparse.ArgumentParser):
	parser.add_argument(
		"--help",
		"-h",
		action=HelpAction,
		help="show this help message and exit",
	)


def add_values(parser: argparse.ArgumentParser, runnable: type[Runnable]):
	parser._positionals.title = "arguments"
	for value in runnable.settled().values():
		if isinstance(value, Argument):
			add_argument(parser, value)
		else:
			add_option(parser, value)


def add_argument(parser: argparse.ArgumentParser, argument: Argument):
	if argument.required:
		parser.add_argument(
			argument.name,
			type=converter(argument.type),
			metavar=f"<{argument.name}>",
			help=help_text(argument.help, argument.type),
		)
	else:
		parser.add_argument(
			argument.name,
			type=converter(argument.type),
			nargs="?",
			default=argument.initial,
			metavar=f"<{argument.name}>",
			help=help_text(argument.help, argument.type),
		)


def add_option(parser: argparse.ArgumentParser, option: Option):
	option_strings = [f"--{option.name}"]
	if option.short is not None:
		option_strings.append(f"-{option.short}")

	if option.flag:
		parser.add_argument(
			*option_strings,
			dest=option.name,
			action="store_true",
			default=option.initial,
			help=help_text(option.help, option.type),
		)
	elif option.repeated:
		parser.add_argument(
			*option_strings,
			dest=option.name,
			action="append",
			type=converter(option.item_type),
			default=None,
			metavar=f"<{option.name}>",
			help=help_text(option.help, option.item_type),
		)
	else:
		parser.add_argument(
			*option_strings,
			dest=option.name,
			type=converter(option.type),
			required=option.required,
			default=None if option.required else option.initial,
			metavar=f"<{option.name}>",
			help=help_text(option.help, option.type),
		)


def converter(value_type: Any) -> Callable[[str], object]:
	if not choices(value_type):
		return value_type

	def convert(text: str) -> StrEnum:
		try:
			return value_type(text)
		except ValueError:
			raise argparse.ArgumentTypeError(
				f"invalid choice: {text!r} (choose from {listing(value_type)})"
			) from None

	return convert


def help_text(help: str | None, value_type: Any) -> str | None:
	help = escape(help)
	if not choices(value_type):
		return help

	listed = f"choices: {listing(value_type)}"
	if help is None:
		return listed
	else:
		return f"{help} ({listed})"


def listing(choice_type: type[StrEnum]) -> str:
	return ", ".join(member.value for member in choice_type)


def escape(help: str | None) -> str | None:
	if help is None:
		return None

	return help.replace("%", "%%")


def parse_program(program: type[Program], argv: list[str]) -> ParseResult:
	parser = create_parser(program)
	add_values(parser, program)
	namespace = parser.parse_args(argv)
	return ParseResult(program, None, parse_values(namespace, program))


def parse_commands(program: type[Program], argv: list[str]) -> ParseResult:
	parser = create_parser(program)
	add_commands(parser, program.commands)

	if not argv:
		raise CommandMissing(parser.format_help())

	if argv[0] == "--":
		parser.error("argument command: invalid choice: '--'")

	namespace = parser.parse_args(argv)
	command_name = getattr(namespace, COMMAND_DESTINATION)
	command = next(
		command for command in program.commands if command.name == command_name
	)
	return ParseResult(program, command, parse_values(namespace, command))


def parse_values(
	namespace: argparse.Namespace,
	runnable: type[Runnable],
) -> dict[str, object]:
	values = {}
	for name, value in runnable.settled().items():
		parsed = getattr(namespace, name)
		if isinstance(value, Option) and value.repeated and parsed is None:
			values[name] = value.initial
		else:
			values[name] = parsed
	return values
