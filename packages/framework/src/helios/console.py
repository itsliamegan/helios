from luna.cli import Program

import helios.assets.command
import helios.database.migration.command
import helios.session.command
import helios.wsgi.command


class Program(Program):
	name = "helios"
	commands = (
		helios.wsgi.command.Serve,
		helios.assets.command.Compile,
		helios.database.migration.command.Migrate,
		helios.database.migration.command.Status,
		helios.session.command.MakeMigration,
	)
