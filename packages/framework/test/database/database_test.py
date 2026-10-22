from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_is_not, assert_raises

from helios.database import Config, Database, DatabaseBusyError, Model
from helios.database.registry import Registry
from helios.database.sqlite import connect

SCHEMA = """
CREATE TABLE posts (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	title TEXT NOT NULL
)
"""


class Post(Model):
	table = "posts"

	title: str


def test_transaction_commits_when_block_ends():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		database = Database(Config(path), Registry([Post]))

		with database.transaction() as store:
			store.create(Post, title="Intro")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [("Intro",)])


def test_transaction_rolls_back_when_block_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		database = Database(Config(path), Registry([Post]))

		with assert_raises(ValueError), database.transaction() as store:
			store.create(Post, title="Intro")
			raise ValueError("failed")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [])


def test_transaction_holds_write_lock():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		database = Database(Config(path), Registry([Post]))
		other = connect(Config(path, busy_timeout=timedelta(milliseconds=10)))

		try:
			with database.transaction(), assert_raises(DatabaseBusyError):
				other.begin()
		finally:
			other.close()


def test_each_transaction_opens_its_own_connection():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		database = Database(Config(path), Registry([Post]))

		with database.transaction() as first:
			pass
		with database.transaction() as second:
			pass

		assert_is_not(first.connection, second.connection)
