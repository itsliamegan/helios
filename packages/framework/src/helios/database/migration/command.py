from typing import Any

from luna.cli import Command, option

from helios.app import Application
from helios.database.config import Config
from helios.database.error import DatabaseError

from .migrations import Migrations
from .migrator import Migrator


class Migrate(Command):
	"""Apply pending migrations to the database."""

	name = "migrate"
	dry: bool = option(
		default=False,
		short="d",
		help="report the migrations that would be applied without applying them",
	)

	def __init__(self, application: Application, **values: Any):
		super().__init__(**values)
		self.application = application

	def run(self):
		container = self.application.container
		if not container.bound(Config):
			self.fail("the application has no database configuration")
		config = container.get(Config)

		try:
			migrations = Migrations.load(config.migrations)
		except DatabaseError as error:
			self.fail(str(error))
		migrator = Migrator(config, migrations)

		if self.dry:
			self.preview(migrator)
		else:
			self.apply(migrator)

	def apply(self, migrator: Migrator):
		try:
			applied = migrator.apply()
		except DatabaseError as error:
			self.report_version(migrator)
			self.fail(str(error))

		for migration in applied:
			self.logger.info(f"apply  {migration.name}")
		self.report_version(migrator)

	def preview(self, migrator: Migrator):
		try:
			pending = migrator.pending()
		except DatabaseError as error:
			self.fail(str(error))

		for migration in pending:
			self.logger.info(f"apply  {migration.name}")
		self.logger.info("dry run: nothing applied")

	def report_version(self, migrator: Migrator):
		"""Report the database version, if the database can be read."""

		try:
			version = migrator.version()
		except DatabaseError:
			return
		self.logger.info(f"database at version {version}")


class Status(Command):
	"""Report the database version and pending migrations."""

	name = "migrate:status"

	def __init__(self, application: Application, **values: Any):
		super().__init__(**values)
		self.application = application

	def run(self):
		container = self.application.container
		if not container.bound(Config):
			self.fail("the application has no database configuration")
		config = container.get(Config)

		try:
			migrations = Migrations.load(config.migrations)
			status = Migrator(config, migrations).status()
		except DatabaseError as error:
			self.fail(str(error))

		self.logger.info(f"current  {status.current}")
		self.logger.info(f"latest   {status.latest}")
		if status.current > status.latest:
			self.logger.info("database is newer than the latest migration")
		for migration in status.pending:
			self.logger.info(f"pending  {migration.name}")
