from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_not, assert_raises

from helios.database.migration import (
	ForeignKeyError,
	MigrationError,
	Migrations,
	Migrator,
)


class Scratch:
	"""A temporary migrations directory and database file."""

	def __init__(self):
		self.temp_dir = TemporaryDirectory()
		self.dir = Path(self.temp_dir.name)
		self.migrations = self.dir.joinpath("migrations")
		self.migrations.mkdir()
		self.path = self.dir.joinpath("app.sqlite")

	def __enter__(self):
		return self

	def __exit__(self, exception_type, exception, traceback):
		self.temp_dir.cleanup()

	def migrator(self, path: Path | None = None) -> Migrator:
		return Migrator(path or self.path, Migrations.load(self.migrations))

	def write(self, name: str, sql: str):
		self.migrations.joinpath(name).write_text(sql)

	def query(self, sql: str) -> list[tuple]:
		connection = sqlite3.connect(self.path)
		try:
			return connection.execute(sql).fetchall()
		finally:
			connection.close()

	def version(self) -> int:
		return self.query("PRAGMA user_version")[0][0]

	def tables(self) -> list[str]:
		return [
			name
			for (name,) in self.query(
				"SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
			)
		]


def names(migrations) -> list[str]:
	return [migration.name for migration in migrations]


def test_applies_every_migration_to_a_fresh_database():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_authors.sql",
			"CREATE TABLE authors (id INTEGER PRIMARY KEY);\n",
		)
		scratch.write(
			"0002_create_posts.sql",
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n",
		)

		applied = scratch.migrator().apply()

		assert_eq(names(applied), ["0001_create_authors", "0002_create_posts"])
		assert_eq(scratch.version(), 2)
		assert_eq(scratch.tables(), ["authors", "posts"])


def test_second_apply_does_nothing():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_authors.sql",
			"CREATE TABLE authors (id INTEGER PRIMARY KEY);\n",
		)
		scratch.migrator().apply()

		applied = scratch.migrator().apply()

		assert_eq(applied, [])
		assert_eq(scratch.version(), 1)


def test_applies_only_migrations_after_the_current_version():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_authors.sql",
			"CREATE TABLE authors (id INTEGER PRIMARY KEY);\n",
		)
		scratch.migrator().apply()
		scratch.write(
			"0002_create_posts.sql",
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n",
		)

		applied = scratch.migrator().apply()

		assert_eq(names(applied), ["0002_create_posts"])
		assert_eq(scratch.version(), 2)
		assert_eq(scratch.tables(), ["authors", "posts"])


def test_failing_statement_rolls_back_its_whole_migration():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_authors.sql",
			"CREATE TABLE authors (id INTEGER PRIMARY KEY);\n",
		)
		scratch.write(
			"0002_create_posts.sql",
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n"
			"INSERT INTO missing VALUES (1);\n",
		)

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_eq(scratch.version(), 1)
		assert_eq(scratch.tables(), ["authors"])


def test_foreign_key_violation_rolls_back_the_migration():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_initial_schema.sql",
			"CREATE TABLE posts (id INTEGER PRIMARY KEY);\n"
			"CREATE TABLE comments (\n"
			"\tid INTEGER PRIMARY KEY,\n"
			"\tpost_id INTEGER REFERENCES posts (id)\n"
			");\n",
		)
		scratch.write(
			"0002_add_orphan_to_comments.sql",
			"INSERT INTO comments VALUES (1, 99);\n",
		)

		with assert_raises(ForeignKeyError) as raised:
			scratch.migrator().apply()

		assert_eq(raised.exception.violations, [("comments", 1, "posts", 0)])
		assert_eq(scratch.version(), 1)
		assert_eq(scratch.query("SELECT * FROM comments"), [])


def test_rebuilds_a_table_that_other_tables_reference():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_initial_schema.sql",
			"CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT);\n"
			"CREATE TABLE comments (\n"
			"\tid INTEGER PRIMARY KEY,\n"
			"\tpost_id INTEGER REFERENCES posts (id) ON DELETE CASCADE\n"
			");\n"
			"INSERT INTO posts VALUES (1, 'Intro');\n"
			"INSERT INTO comments VALUES (1, 1);\n",
		)
		scratch.write(
			"0002_change_title_in_posts.sql",
			"CREATE TABLE new_posts (id INTEGER PRIMARY KEY, title TEXT NOT NULL);\n"
			"INSERT INTO new_posts SELECT id, title FROM posts;\n"
			"DROP TABLE posts;\n"
			"ALTER TABLE new_posts RENAME TO posts;\n",
		)

		scratch.migrator().apply()

		assert_eq(scratch.version(), 2)
		assert_eq(scratch.query("SELECT * FROM posts"), [(1, "Intro")])
		assert_eq(scratch.query("SELECT * FROM comments"), [(1, 1)])


def test_refuses_a_gap_in_numbering():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		scratch.write("0003_create_posts.sql", "CREATE TABLE posts (id INTEGER);\n")

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_not(scratch.path.exists())


def test_refuses_a_duplicate_number():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		scratch.write("0001_create_posts.sql", "CREATE TABLE posts (id INTEGER);\n")

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_not(scratch.path.exists())


def test_refuses_a_malformed_filename():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		scratch.write("2_Posts.sql", "CREATE TABLE posts (id INTEGER);\n")

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_not(scratch.path.exists())


def test_refuses_transaction_control_statements():
	with Scratch() as scratch:
		scratch.write(
			"0001_create_authors.sql",
			"CREATE TABLE authors (id INTEGER);\n/* sneaky */ COMMIT;\n",
		)

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_not(scratch.path.exists())


def test_refuses_a_database_newer_than_the_latest_migration():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		connection = sqlite3.connect(scratch.path)
		connection.execute("PRAGMA user_version = 5")
		connection.close()

		with assert_raises(MigrationError):
			scratch.migrator().apply()

		assert_eq(scratch.version(), 5)
		assert_eq(scratch.tables(), [])


def test_pending_lists_migrations_without_applying_them():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		scratch.migrator().apply()
		scratch.write("0002_create_posts.sql", "CREATE TABLE posts (id INTEGER);\n")

		pending = scratch.migrator().pending()

		assert_eq(names(pending), ["0002_create_posts"])
		assert_eq(scratch.version(), 1)
		assert_eq(scratch.tables(), ["authors"])


def test_status_reports_current_latest_and_pending():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		scratch.migrator().apply()
		scratch.write("0002_create_posts.sql", "CREATE TABLE posts (id INTEGER);\n")

		result = scratch.migrator().status()

		assert_eq(result.current, 1)
		assert_eq(result.latest, 2)
		assert_eq(names(result.pending), ["0002_create_posts"])


def test_status_and_pending_refuse_a_missing_database():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")

		with assert_raises(MigrationError):
			scratch.migrator().status()
		with assert_raises(MigrationError):
			scratch.migrator().pending()

		assert_not(scratch.path.exists())


def test_apply_refuses_a_missing_database_directory():
	with Scratch() as scratch:
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")
		path = scratch.dir.joinpath("missing", "app.sqlite")

		with assert_raises(MigrationError):
			scratch.migrator(path).apply()

		assert_not(path.parent.exists())


def test_ignores_hidden_files():
	with Scratch() as scratch:
		scratch.write(".gitkeep", "")
		scratch.write(".0002_create_posts.sql.swp", "not sql")
		scratch.write("0001_create_authors.sql", "CREATE TABLE authors (id INTEGER);\n")

		applied = scratch.migrator().apply()

		assert_eq(names(applied), ["0001_create_authors"])
		assert_eq(scratch.version(), 1)
