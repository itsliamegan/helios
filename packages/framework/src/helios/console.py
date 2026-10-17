from luna.cli import Program

from helios.wsgi.command import Serve


class Program(Program):
	name = "helios"
	commands = (Serve,)
