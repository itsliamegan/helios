from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

import helios.app
from helios.app import Application
from helios.console import Program
from helios.database import Config
from helios.database.migration import Migrations, Migrator
from helios.database.provider import Provider
from helios.routing import Router
from helios.session.database import SCHEMA


def test_writes_the_migration_at_the_next_number():
	with TemporaryDirectory() as directory:
		migrations = Path(directory, "migrations")
		migrations.mkdir()
		Path(migrations, "0001_create_posts.sql").write_text(
			"CREATE TABLE posts (id TEXT PRIMARY KEY);\n"
		)
		app = Application(
			helios.app.Config(),
			Router([]),
			[Provider(Config(Path(directory, "app.sqlite"), migrations), [])],
		)

		with redirect_stderr(StringIO()):
			Program.main(["sessions:migration"], app)

		names = sorted(path.name for path in migrations.iterdir())
		written = Path(migrations, "0002_create_sessions.sql").read_text()

	assert_eq(names, ["0001_create_posts.sql", "0002_create_sessions.sql"])
	assert_eq(written, SCHEMA)


def test_written_migration_applies():
	with TemporaryDirectory() as directory:
		migrations = Path(directory, "migrations")
		migrations.mkdir()
		path = Path(directory, "app.sqlite")
		app = Application(
			helios.app.Config(),
			Router([]),
			[Provider(Config(path, migrations), [])],
		)
		with redirect_stderr(StringIO()):
			Program.main(["sessions:migration"], app)

		Migrator(path, Migrations.load(migrations)).apply()

		connection = sqlite3.connect(path)
		try:
			tables = connection.execute(
				"SELECT name FROM sqlite_schema WHERE type = 'table'"
			).fetchall()
		finally:
			connection.close()

	assert_eq(tables, [("sessions",)])


def test_fails_without_a_database_configuration():
	app = Application(helios.app.Config(), Router([]), [])

	with redirect_stderr(StringIO()), assert_raises(SystemExit) as raised:
		Program.main(["sessions:migration"], app)

	assert_eq(raised.exception.code, 1)
