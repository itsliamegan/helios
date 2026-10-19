from contextlib import chdir, redirect_stderr
from io import StringIO
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_not, assert_raises

import helios.app
from helios.app import Application
from helios.console import Program
from helios.database import Config, Provider
from helios.routing import Router


def test_migrate_applies_migrations_from_the_default_directory():
	app = Application(
		helios.app.Config(),
		Router([]),
		[Provider(Config(Path("app.sqlite")), [])],
	)

	with TemporaryDirectory() as directory, chdir(directory):
		Path("database", "migrations").mkdir(parents=True)
		Path("database", "migrations", "0001_create_posts.sql").write_text(
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n"
		)
		with redirect_stderr(StringIO()):
			Program.main(["migrate"], app)

		connection = sqlite3.connect(Path(directory, "app.sqlite"))
		try:
			version = connection.execute("PRAGMA user_version").fetchone()[0]
		finally:
			connection.close()

	assert_eq(version, 1)


def test_migrate_dry_run_leaves_the_database_unchanged():
	with TemporaryDirectory() as directory:
		migrations = Path(directory, "migrations")
		migrations.mkdir()
		Path(migrations, "0001_create_posts.sql").write_text(
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n"
		)
		path = Path(directory, "app.sqlite")
		sqlite3.connect(path).close()
		app = Application(
			helios.app.Config(),
			Router([]),
			[Provider(Config(path, migrations=migrations), [])],
		)

		with redirect_stderr(StringIO()):
			Program.main(["migrate", "--dry"], app)

		connection = sqlite3.connect(path)
		try:
			version = connection.execute("PRAGMA user_version").fetchone()[0]
		finally:
			connection.close()

	assert_eq(version, 0)


def test_migrate_fails_without_a_database_configuration():
	app = Application(helios.app.Config(), Router([]), [])

	with redirect_stderr(StringIO()), assert_raises(SystemExit) as raised:
		Program.main(["migrate"], app)

	assert_eq(raised.exception.code, 1)


def test_status_refuses_a_missing_database():
	with TemporaryDirectory() as directory:
		migrations = Path(directory, "migrations")
		migrations.mkdir()
		path = Path(directory, "app.sqlite")
		app = Application(
			helios.app.Config(),
			Router([]),
			[Provider(Config(path, migrations=migrations), [])],
		)

		with redirect_stderr(StringIO()), assert_raises(SystemExit) as raised:
			Program.main(["migrate:status"], app)

		assert_eq(raised.exception.code, 1)
		assert_not(path.exists())


def test_status_fails_without_a_database_configuration():
	app = Application(helios.app.Config(), Router([]), [])

	with redirect_stderr(StringIO()), assert_raises(SystemExit) as raised:
		Program.main(["migrate:status"], app)

	assert_eq(raised.exception.code, 1)
