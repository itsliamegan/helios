from luna.cli import Program

from helios.assets.command import Compile
from helios.database.migration.command import Migrate, Status
from helios.wsgi.command import Serve


class Program(Program):
	name = "helios"
	commands = (Serve, Compile, Migrate, Status)
