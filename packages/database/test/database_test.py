from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_is, assert_is_not, assert_raises

from helios.database import Database, DatabaseBusyError, DatabaseError, Model
from helios.database.registry import Registry
from helios.database.sqlite import Connection

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


def test_connection_commits_each_statement():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.connection() as connection:
			connection.execute("CREATE TABLE tags (name TEXT NOT NULL)").close()
			connection.execute("INSERT INTO tags (name) VALUES ('python')").close()
			observer = sqlite3.connect(path)
			try:
				rows = observer.execute("SELECT name FROM tags").fetchall()
			finally:
				observer.close()

		assert_eq(rows, [("python",)])


def test_read_only_connection_refuses_writes():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with (
			database.connection(read_only=True) as connection,
			assert_raises(DatabaseError),
		):
			connection.execute("DELETE FROM posts")


def test_transaction_commits_statements_when_block_ends():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute("CREATE TABLE tags (name TEXT NOT NULL)")
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.transaction() as transaction:
			transaction.execute("INSERT INTO tags (name) VALUES ('python')").close()

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT name FROM tags").fetchall()
		connection.close()
		assert_eq(rows, [("python",)])


def test_transaction_without_statements_leaves_write_lock_free():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)
		other = Connection.open(path, busy_timeout=timedelta(milliseconds=10))

		try:
			with database.transaction():
				other.begin()
				other.rollback()
		finally:
			other.close()


def test_transaction_holds_write_lock_from_first_read():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)
		other = Connection.open(path, busy_timeout=timedelta(milliseconds=10))

		try:
			with database.store() as store:
				store.find_all(Post)
				with assert_raises(DatabaseBusyError):
					other.begin()
		finally:
			other.close()


def test_each_transaction_opens_its_own_connection():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.transaction() as first:
			pass
		with database.transaction() as second:
			pass

		assert_is_not(first.connection, second.connection)


def test_store_commits_when_block_ends():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.store() as store:
			store.create(Post, title="Intro")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [("Intro",)])


def test_store_rolls_back_when_block_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with assert_raises(ValueError), database.store() as store:
			store.create(Post, title="Intro")
			raise ValueError("failed")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [])


def test_store_refuses_work_after_block_commits():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.store() as store:
			pass

		with assert_raises(RuntimeError) as raised:
			store.create(Post, title="Intro")
		assert_is(type(raised.exception), RuntimeError)


def test_store_refuses_work_after_block_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with assert_raises(ValueError), database.store() as store:
			raise ValueError("failed")

		with assert_raises(RuntimeError) as raised:
			store.create(Post, title="Intro")
		assert_is(type(raised.exception), RuntimeError)


def test_connection_inside_transaction_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.transaction():
			with assert_raises(RuntimeError) as raised, database.connection():
				pass
			assert_is(type(raised.exception), RuntimeError)


def test_transaction_inside_transaction_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.transaction():
			with assert_raises(RuntimeError) as raised, database.transaction():
				pass
			assert_is(type(raised.exception), RuntimeError)


def test_store_inside_transaction_raises():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with database.transaction():
			with assert_raises(RuntimeError) as raised, database.store():
				pass
			assert_is(type(raised.exception), RuntimeError)


def test_transaction_opens_after_previous_transaction_ends():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(path, registry)

		with assert_raises(ValueError), database.store():
			raise ValueError("failed")
		with database.store() as store:
			store.create(Post, title="Intro")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [("Intro",)])


def test_transaction_on_another_database_opens_inside_transaction():
	with TemporaryDirectory() as directory:
		path = Path(directory, "archive.sqlite")
		connection = sqlite3.connect(path, autocommit=True)
		connection.execute(SCHEMA)
		connection.close()
		registry = Registry()
		registry.model(Post)
		database = Database(Path(directory, "app.sqlite"), registry)
		registry = Registry()
		registry.model(Post)
		archive = Database(path, registry)

		with database.transaction(), archive.store() as store:
			store.create(Post, title="Intro")

		connection = sqlite3.connect(path)
		rows = connection.execute("SELECT title FROM posts").fetchall()
		connection.close()
		assert_eq(rows, [("Intro",)])
