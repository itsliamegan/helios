import sqlite3
from typing import Any

from luna.cli import Command, option

from helios.app import Application

from .config import Config
from .migration import MigrationError, Migrations, Migrator


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
		except MigrationError as error:
			self.fail(describe(error))
		migrator = Migrator(config, migrations)

		if self.dry:
			self.preview(migrator)
		else:
			self.apply(migrator)

	def apply(self, migrator: Migrator):
		try:
			applied = migrator.apply()
		except MigrationError as error:
			self.report_version(migrator)
			self.fail(describe(error))

		for migration in applied:
			self.logger.info(f"apply  {migration.name}")
		self.report_version(migrator)

	def preview(self, migrator: Migrator):
		try:
			pending = migrator.pending()
		except MigrationError as error:
			self.fail(describe(error))

		for migration in pending:
			self.logger.info(f"apply  {migration.name}")
		self.logger.info("dry run: nothing applied")

	def report_version(self, migrator: Migrator):
		"""Report the database version, if the database can be read."""

		try:
			version = migrator.version()
		except MigrationError:
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
		except MigrationError as error:
			self.fail(describe(error))

		self.logger.info(f"current  {status.current}")
		self.logger.info(f"latest   {status.latest}")
		if status.current > status.latest:
			self.logger.info("database is newer than the latest migration")
		for migration in status.pending:
			self.logger.info(f"pending  {migration.name}")


def describe(error: MigrationError) -> str:
	"""Describe the error, followed by the SQLite error that caused it."""

	cause = error.__cause__
	while cause is not None:
		if isinstance(cause, sqlite3.Error):
			return f"{error}\nsqlite: {cause}"
		cause = cause.__cause__
	return str(error)
