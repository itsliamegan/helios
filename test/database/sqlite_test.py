from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import (
	assert_eq,
	assert_is_instance,
	assert_not_in,
	assert_raises,
	assert_that,
)

from helios.database import Config, DatabaseBusyError, DatabaseError
from helios.database.sqlite import connect


def create_database(path: Path, schema: str):
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.executescript(schema)
	finally:
		connection.close()


def test_commits_transaction_visible_to_separate_connection():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, "CREATE TABLE posts (title TEXT NOT NULL)")
		connection = connect(Config(path))
		try:
			connection.begin()
			connection.execute(
				"INSERT INTO posts (title) VALUES (?)", ("Intro",)
			).close()
			connection.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(
				observer.execute("SELECT title FROM posts").fetchone(), ("Intro",)
			)
		finally:
			observer.close()


def test_rolls_back_transaction():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, "CREATE TABLE posts (title TEXT NOT NULL)")
		connection = connect(Config(path))
		try:
			connection.begin()
			connection.execute(
				"INSERT INTO posts (title) VALUES (?)", ("Intro",)
			).close()
			connection.rollback()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(observer.execute("SELECT title FROM posts").fetchall(), [])
		finally:
			observer.close()


def test_enforces_foreign_keys():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			"""
			CREATE TABLE authors (id TEXT PRIMARY KEY);
			CREATE TABLE posts (
				author_id TEXT NOT NULL REFERENCES authors (id)
			);
			""",
		)
		connection = connect(Config(path))
		try:
			connection.begin()
			with assert_raises(DatabaseError) as raised:
				connection.execute(
					"INSERT INTO posts (author_id) VALUES (?)", ("missing",)
				)
			exception = raised.exception
			assert_is_instance(exception.__cause__, sqlite3.IntegrityError)
		finally:
			connection.close()


def test_translates_writer_contention_to_database_busy():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, "CREATE TABLE posts (title TEXT NOT NULL)")
		first = connect(Config(path))
		second = connect(Config(path, timedelta(milliseconds=10)))
		try:
			first.begin()
			with assert_raises(DatabaseBusyError) as raised:
				second.begin()
			exception = raised.exception
			assert_is_instance(exception.__cause__, sqlite3.OperationalError)
		finally:
			second.close()
			first.close()


def test_translates_statement_errors_without_bound_values():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		secret = "distinctive-secret-value"
		connection = connect(Config(path))
		try:
			connection.begin()
			with assert_raises(DatabaseError) as raised:
				connection.execute("INSERT INTO missing (value) VALUES (?)", (secret,))

			exception = raised.exception
			assert_is_instance(exception.__cause__, sqlite3.Error)
			assert_not_in(secret, str(exception))
		finally:
			connection.close()


def test_cursor_reports_changed_rows():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, "CREATE TABLE posts (title TEXT NOT NULL)")
		connection = connect(Config(path))
		try:
			connection.begin()
			connection.execute("INSERT INTO posts VALUES ('A'), ('B')").close()

			matching_two = connection.execute("UPDATE posts SET title = 'C'")
			matching_none = connection.execute(
				"UPDATE posts SET title = 'D' WHERE title = 'missing'"
			)
			try:
				assert_eq(matching_two.changed_rows, 2)
				assert_eq(matching_none.changed_rows, 0)
			finally:
				matching_two.close()
				matching_none.close()
		finally:
			connection.close()


def test_reports_the_bound_parameter_limit():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = connect(Config(path))
		try:
			default = connection.parameter_limit
			connection.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 3)

			assert_that(default > 3)
			assert_eq(connection.parameter_limit, 3)
		finally:
			connection.close()
