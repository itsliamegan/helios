from pathlib import Path
import shutil
from typing import Any

from luna.cli import Command

from helios.app import Application
import helios.database
from helios.database.migration import MigrationError, Migrations

SKELETON_FILE = Path(Path(__file__).parent, "skeleton", "create_sessions.sql")


class MakeMigration(Command):
	"""Write the migration that creates the session table.

	The migration takes the next number in the migrations directory, and the
	application owns it from then on.
	"""

	name = "sessions:migration"

	def __init__(self, application: Application, **values: Any):
		super().__init__(**values)
		self.application = application

	def run(self):
		container = self.application.container
		if not container.bound(helios.database.Config):
			self.fail("the application has no database configuration")
		config = container.get(helios.database.Config)
		try:
			migrations = Migrations.load(config.migrations)
		except MigrationError as error:
			self.fail(str(error))

		path = Path(
			config.migrations,
			f"{migrations.latest + 1:04d}_create_sessions.sql",
		)
		shutil.copyfile(SKELETON_FILE, path)
		self.logger.info(f"create  {path}")
