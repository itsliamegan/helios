import sys
from typing import Any, ClassVar

from luna.cli.command import Command
from luna.cli.parse import CommandMissing, HelpRequested, ParseError, parse
from luna.cli.runnable import Runnable
from luna.declarative import check_single_base


class Program(Runnable):
	commands: ClassVar[tuple[type[Command], ...]] = ()

	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Program, ValueError)
		cls.declare()

		direct = "run" in vars(cls)
		if "commands" in vars(cls):
			if direct or cls.declared:
				raise ValueError(
					f"{cls.__name__} cannot declare both commands and values or run()"
				)
			check_commands(cls)
		elif not direct:
			raise ValueError(f"{cls.__name__} must declare commands or override run()")

	@classmethod
	def main(cls, argv: list[str]) -> object:
		# If the provided argv includes the current program, drop it.
		if argv and argv[0] == sys.argv[0]:
			argv = argv[1:]

		try:
			result = parse(cls, argv)
		except HelpRequested as requested:
			print(requested.help, end="")
			return None
		except CommandMissing as missing:
			print(missing.help, end="", file=sys.stderr)
			raise SystemExit(2) from None
		except ParseError as error:
			print(error.usage, end="", file=sys.stderr)
			print(f"{cls.name}: error: {error.message}", file=sys.stderr)
			raise SystemExit(2) from None

		if result.command is not None:
			return result.command(**result.values).run()
		else:
			return result.program(**result.values).run()


def check_commands(program: type[Program]):
	commands = program.commands
	if not commands:
		raise ValueError(f"{program.__name__}.commands must list at least one command")

	names = set()
	for command in commands:
		if not isinstance(command, type) or not issubclass(command, Command):
			# Invalid declarations raise ValueError at class creation.
			raise ValueError(  # noqa: TRY004
				f"{program.__name__}.commands contains a non-Command entry: {command!r}"
			)
		if command.name in names:
			raise ValueError(
				f"{program.__name__}.commands has duplicate name: {command.name!r}"
			)
		names.add(command.name)
