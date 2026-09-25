from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any, cast
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios import http
from helios.database import (
	Config,
	DatabaseError,
	Lifecycle,
	Model,
	ModelError,
	NotFoundError,
	Store,
)
from helios.database.sqlite import connect


class Token:
	def __init__(self, value: str):
		self.value = value

	@classmethod
	def check(cls, value: object):
		if not isinstance(value, cls):
			raise TypeError("expected a Token")

	@classmethod
	def encode(cls, value: Token):
		cls.check(value)
		return value.value

	@classmethod
	def decode(cls, value: float | str | bytes):
		if not isinstance(value, str):
			raise TypeError("expected token text")
		return cls(value)


class Record(Model):
	table = "records"

	name: str
	count: int
	active: bool
	owner_id: UUID
	link: http.URL
	published_at: datetime
	note: str | None = None
	token: Token


SCHEMA = """
CREATE TABLE records (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL CHECK (name <> ''),
	count INTEGER NOT NULL,
	active INTEGER NOT NULL CHECK (active IN (0, 1)),
	owner_id TEXT NOT NULL,
	link TEXT NOT NULL,
	published_at TEXT NOT NULL,
	note TEXT,
	token TEXT NOT NULL
);
"""


def create_database(path: Path, schema: str = SCHEMA):
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.executescript(schema)
	finally:
		connection.close()


def record_values(name: str = "Intro"):
	return {
		"name": name,
		"count": 3,
		"active": True,
		"owner_id": uuid4(),
		"link": http.URL("https://example.com/posts/intro"),
		"published_at": datetime(2025, 1, 2, 3, 4, 5, 6, tzinfo=UTC),
		"token": Token("secret"),
	}


def test_crud_and_scalar_round_trip():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		connection.begin()
		store = Store(connection, [Record])
		try:
			created = store.create(Record, **record_values())
			found = store.find_one(Record, created.id)
			assert_that(found is created)
			assert_eq(store.find_all(Record), [created])
			assert_eq(store.find_by(Record, active=True), [created])
			assert_that(isinstance(found.id, UUID))
			assert_eq(found.created_at.tzinfo, UTC)
			assert_eq(found.count, 3)
			assert_eq(found.active, True)
			assert_that(isinstance(found.owner_id, UUID))
			assert_that(isinstance(found.link, http.URL))
			assert_eq(found.published_at.tzinfo, UTC)
			assert_that(found.note is None)
			assert_eq(found.token.value, "secret")

			created.name = "Revised"
			store.save(created)
			connection.commit()
		finally:
			connection.close()

		second_connection = connect(Config(path))
		second_connection.begin()
		try:
			reloaded = Store(second_connection, [Record]).find_one(Record, created.id)
			assert_eq(reloaded.name, "Revised")
			assert_eq(reloaded.active, True)
			assert_eq(reloaded.owner_id, created.owner_id)
			assert_eq(str(reloaded.link), str(created.link))
			assert_eq(reloaded.published_at, created.published_at)
			assert_that(reloaded.note is None)
			assert_eq(reloaded.token.value, "secret")
		finally:
			second_connection.close()


def test_failed_insert_leaves_model_new_for_later_save():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		connection.begin()
		store = Store(connection, [Record])
		model = Record(**record_values(name=""))
		try:
			with assert_raises(DatabaseError):
				store.save(model)
			with assert_raises(AttributeError):
				_ = model.created_at

			model.name = "Valid"
			store.save(model)
			assert_that(isinstance(model.created_at, datetime))
			assert_that(store.find_one(Record, model.id) is model)
		finally:
			connection.close()


def test_failed_update_preserves_assignment_for_retry():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			SCHEMA
			+ """
			CREATE TABLE controls (updates_allowed INTEGER NOT NULL);
			INSERT INTO controls VALUES (0);
			CREATE TRIGGER block_record_update
			BEFORE UPDATE ON records
			WHEN (SELECT updates_allowed FROM controls) = 0
			BEGIN
				SELECT RAISE(ABORT, 'updates blocked');
			END;
			""",
		)
		connection = connect(Config(path))
		connection.begin()
		store = Store(connection, [Record])
		try:
			model = store.create(Record, **record_values())
			model.name = "Revised"
			with assert_raises(DatabaseError):
				store.save(model)

			connection.execute("UPDATE controls SET updates_allowed = 1").close()
			store.save(model)
			connection.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(
				observer.execute("SELECT name FROM records").fetchone(),
				("Revised",),
			)
		finally:
			observer.close()


def test_unchanged_save_issues_no_update():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			SCHEMA
			+ """
			CREATE TABLE update_log (record_id TEXT NOT NULL);
			CREATE TRIGGER log_record_update AFTER UPDATE ON records
			BEGIN
				INSERT INTO update_log VALUES (NEW.id);
			END;
			""",
		)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [Record])
			model = store.create(Record, **record_values())
			with assert_raises(ModelError):
				model.count = True
			store.save(model)
			connection.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(observer.execute("SELECT * FROM update_log").fetchall(), [])
		finally:
			observer.close()


def test_save_updates_only_assigned_columns():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			SCHEMA
			+ """
			CREATE TABLE update_log (record_id TEXT NOT NULL);
			CREATE TABLE count_update_log (record_id TEXT NOT NULL);
			CREATE TRIGGER log_record_update AFTER UPDATE ON records
			BEGIN
				INSERT INTO update_log VALUES (NEW.id);
			END;
			CREATE TRIGGER log_count_update AFTER UPDATE OF count ON records
			BEGIN
				INSERT INTO count_update_log VALUES (NEW.id);
			END;
			""",
		)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [Record])
			model = store.create(Record, **record_values())
			model.name = model.name
			store.save(model)
			connection.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(observer.execute("SELECT * FROM count_update_log").fetchall(), [])
			assert_eq(
				observer.execute("SELECT COUNT(*) FROM update_log").fetchone(), (1,)
			)
		finally:
			observer.close()


def test_identity_map_preserves_unsaved_assignment():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [Record])
			model = store.create(Record, **record_values())
			model.name = "Unsaved"

			found = store.find_by(Record, active=True)[0]

			assert_that(found is model)
			assert_eq(found.name, "Unsaved")
		finally:
			connection.close()


def test_tracks_model_lifecycle():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [Record])
			model = Record(**record_values())
			new = model.lifecycle
			store.save(model)
			saved = model.lifecycle
			found = Store(connection, [Record]).find_one(Record, model.id)
			store.delete(model)

			assert_that(new is Lifecycle.NEW)
			assert_that(saved is Lifecycle.SAVED)
			assert_that(found is not model)
			assert_that(found.lifecycle is Lifecycle.SAVED)
			assert_that(model.lifecycle is Lifecycle.DELETED)
		finally:
			connection.close()


def test_deletes_model_and_reports_missing_lookup():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [Record])
			model = store.create(Record, **record_values())
			store.delete(model)

			with assert_raises(NotFoundError) as raised:
				store.find_one(Record, model.id)
			exception = raised.exception
			assert exception is not None
			assert_that(exception.model_type is Record)
			assert_eq(exception.id, model.id)
		finally:
			connection.close()


def test_malformed_stored_scalar_is_database_error():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, SCHEMA.replace(" CHECK (active IN (0, 1))", ""))
		values = record_values()
		raw = sqlite3.connect(path, autocommit=True)
		try:
			raw.execute(
				"""
				INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					str(uuid4()),
					"2025-01-02T03:04:05.000006Z",
					values["name"],
					values["count"],
					2,
					str(values["owner_id"]),
					str(values["link"]),
					"2025-01-02T03:04:05.000006Z",
					None,
					"secret",
				),
			)
		finally:
			raw.close()

		connection = connect(Config(path))
		connection.begin()
		try:
			with assert_raises(DatabaseError):
				Store(connection, [Record]).find_all(Record)
		finally:
			connection.close()


def test_round_trips_models_with_codecs_declared_later():
	class Badge(Model):
		table = "badges"
		label: Label

	class Label:
		def __init__(self, text: str):
			self.text = text

		@classmethod
		def check(cls, value: object):
			if not isinstance(value, cls):
				raise TypeError("expected a Label")

		@classmethod
		def encode(cls, value: Label) -> str:
			return value.text

		@classmethod
		def decode(cls, value: object) -> Label:
			return cls(str(value))

	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			"""CREATE TABLE badges (
				id TEXT PRIMARY KEY,
				created_at TEXT NOT NULL,
				label TEXT NOT NULL
			)""",
		)
		connection = connect(Config(path))
		connection.begin()
		try:
			created = Store(connection, [Badge]).create(Badge, label=Label("new"))
			connection.commit()
		finally:
			connection.close()

		second_connection = connect(Config(path))
		second_connection.begin()
		try:
			found = Store(second_connection, [Badge]).find_one(Badge, created.id)
		finally:
			second_connection.close()

		assert_that(found is not created)
		assert_eq(found.label.text, "new")


def test_quotes_declared_table_and_column_identifiers():
	class OddRecord(Model):
		table = 'odd"records'
		select: str

	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			"""CREATE TABLE "odd""records" (
				id TEXT PRIMARY KEY,
				created_at TEXT NOT NULL,
				"select" TEXT NOT NULL
			)""",
		)
		connection = connect(Config(path))
		connection.begin()
		try:
			store = Store(connection, [OddRecord])
			model = store.create(OddRecord, select="value")

			assert_that(store.find_one(OddRecord, model.id) is model)
			assert_eq(model.select, "value")
		finally:
			connection.close()


def test_validates_registry_and_rejects_unregistered_models():
	class Abstract(Model):
		pass

	class Other(Model):
		table = "others"

	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = connect(Config(path))
		try:
			with assert_raises(ModelError):
				Store(connection, [Abstract])
			with assert_raises(ModelError):
				Store(connection, cast(Any, [object]))

			store = Store(connection, [Record])
			with assert_raises(ModelError):
				store.find_all(Other)
		finally:
			connection.close()
