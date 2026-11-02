from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_is, assert_raises

from helios.database import DatabaseBusyError
from helios.database.sqlite import Connection
from helios.database.transaction import Transaction


def create_database(path: Path):
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.execute("CREATE TABLE posts (title TEXT NOT NULL)")
	finally:
		connection.close()


def test_transaction_without_statements_leaves_write_lock_free():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		other = Connection.open(path, busy_timeout=timedelta(milliseconds=10))
		try:
			Transaction(connection)

			other.begin()
			other.rollback()
		finally:
			other.close()
			connection.close()


def test_first_read_takes_write_lock():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		other = Connection.open(path, busy_timeout=timedelta(milliseconds=10))
		try:
			transaction = Transaction(connection)
			transaction.execute("SELECT title FROM posts").close()

			with assert_raises(DatabaseBusyError):
				other.begin()
		finally:
			other.close()
			connection.close()


def test_commit_makes_writes_visible_to_another_connection():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		try:
			transaction = Transaction(connection)
			transaction.execute(
				"INSERT INTO posts (title) VALUES (?)",
				("Intro",),
			).close()
			transaction.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			rows = observer.execute("SELECT title FROM posts").fetchall()
		finally:
			observer.close()
		assert_eq(rows, [("Intro",)])


def test_rollback_discards_writes():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		try:
			transaction = Transaction(connection)
			transaction.execute(
				"INSERT INTO posts (title) VALUES (?)",
				("Intro",),
			).close()
			transaction.rollback()

			cursor = connection.execute("SELECT title FROM posts")
			try:
				rows = cursor.fetch_all()
			finally:
				cursor.close()
		finally:
			connection.close()
		assert_eq(rows, [])


def test_execute_after_commit_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		try:
			transaction = Transaction(connection)
			transaction.commit()

			with assert_raises(RuntimeError) as raised:
				transaction.execute("SELECT title FROM posts")
			assert_is(type(raised.exception), RuntimeError)
		finally:
			connection.close()


def test_execute_after_rollback_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		try:
			transaction = Transaction(connection)
			transaction.rollback()

			with assert_raises(RuntimeError) as raised:
				transaction.execute("SELECT title FROM posts")
			assert_is(type(raised.exception), RuntimeError)
		finally:
			connection.close()
