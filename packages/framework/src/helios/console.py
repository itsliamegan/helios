from luna.cli import Program

from helios.assets.command import Compile
from helios.wsgi.command import Serve


class Program(Program):
	name = "helios"
	commands = (Serve, Compile)
