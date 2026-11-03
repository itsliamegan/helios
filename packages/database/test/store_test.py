from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid4

from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_is_instance,
	assert_is_not,
	assert_raises,
)

from helios.database import (
	Codec,
	DatabaseError,
	JSON,
	Model,
	ModelError,
	NotFoundError,
	Registry,
	Scalar,
	Store,
)
from helios.database.sqlite import Connection
from helios.database.transaction import Transaction
from helios.url import URL


class Token:
	def __init__(self, value: str):
		self.value = value


class TokenCodec(Codec[Token]):
	converts = Token

	def encode(self, value: Token) -> Scalar:
		return value.value

	def decode(self, value: Scalar) -> Token:
		if not isinstance(value, str):
			raise TypeError("expected token text")
		return Token(value)


class Record(Model):
	table = "records"

	name: str
	count: int
	active: bool
	owner_id: UUID
	link: URL
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
		"link": URL.parse("https://example.com/posts/intro"),
		"published_at": datetime(2025, 1, 2, 3, 4, 5, 6, tzinfo=UTC),
		"token": Token("secret"),
	}


def test_crud_and_scalar_round_trip():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		store = Store(connection, registry)
		try:
			created = store.create(Record, **record_values())
			found = store.find_one(Record, created.id)
			assert_is_not(found, created)
			assert_eq(found.id, created.id)
			assert_eq([item.id for item in store.find_all(Record)], [created.id])
			assert_eq(
				[item.id for item in store.find_by(Record, active=True)],
				[created.id],
			)
			assert_is_instance(found.id, UUID)
			assert_eq(found.created_at.tzinfo, UTC)
			assert_eq(found.count, 3)
			assert_eq(found.active, True)
			assert_is_instance(found.owner_id, UUID)
			assert_is_instance(found.link, URL)
			assert_eq(found.published_at.tzinfo, UTC)
			assert_eq(found.note, None)
			assert_eq(found.token.value, "secret")

			store.update(created, name="Revised")
			connection.commit()
		finally:
			connection.close()

		second_connection = Connection.open(path)
		second_connection.begin()
		try:
			registry = Registry()
			registry.model(Record)
			registry.codec(TokenCodec())
			reloaded = Store(second_connection, registry).find_one(Record, created.id)
			assert_eq(reloaded.name, "Revised")
			assert_eq(reloaded.active, True)
			assert_eq(reloaded.owner_id, created.owner_id)
			assert_eq(str(reloaded.link), str(created.link))
			assert_eq(reloaded.published_at, created.published_at)
			assert_eq(reloaded.note, None)
			assert_eq(reloaded.token.value, "secret")
		finally:
			second_connection.close()


def test_find_by_matches_the_equivalent_query():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		store = Store(connection, registry)
		try:
			created = [
				store.create(Record, **record_values(name))
				for name in ("Alpha", "Beta", "Gamma")
			]

			found = {model.id for model in store.find_by(Record, name="Beta")}
			queried = {
				model.id for model in store.query(Record).where({"name": "Beta"}).all()
			}

			assert_eq(found, {created[1].id})
			assert_eq(found, queried)
		finally:
			connection.close()


def test_find_by_supports_only_column_equality():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		store = Store(connection, registry)
		try:
			store.create(Record, **record_values("Alpha"))

			with assert_raises(ModelError):
				store.find_by(Record, **{"name >=": "Alpha"})
		finally:
			connection.close()


def test_failed_create_leaves_no_row():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		store = Store(connection, registry)
		try:
			with assert_raises(DatabaseError):
				store.create(Record, **record_values(name=""))

			assert_eq(store.find_all(Record), [])
		finally:
			connection.close()


def test_builds_a_model_with_a_naive_datetime_but_refuses_to_store_it():
	values = record_values()
	values["published_at"] = datetime(2025, 1, 2, 3, 4, 5)
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			Record(**values)

			with assert_raises(ModelError):
				store.create(Record, **values)
		finally:
			connection.close()


def test_failed_update_leaves_model_unchanged():
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
		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		store = Store(connection, registry)
		try:
			model = store.create(Record, **record_values())
			original = model.name
			with assert_raises(DatabaseError):
				store.update(model, name="Revised")
			assert_eq(model.name, original)

			connection.execute("UPDATE controls SET updates_allowed = 1").close()
			store.update(model, name="Revised")
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


def test_update_rejects_bad_arguments_before_writing():
	class Other(Model):
		table = "others"

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
		connection = Connection.open(path)
		connection.begin()
		try:
			registry = Registry()
			registry.model(Record)
			registry.codec(TokenCodec())
			store = Store(connection, registry)
			model = store.create(Record, **record_values())
			with assert_raises(ModelError):
				store.update(model)
			with assert_raises(ModelError):
				store.update(model, missing="x")
			with assert_raises(ModelError):
				store.update(model, id=uuid4())
			with assert_raises(ModelError):
				store.update(model, created_at=datetime.now(UTC))
			with assert_raises(ModelError):
				store.update(model, count=True)
			with assert_raises(ModelError):
				store.update(Other(), name="x")
			assert_eq(model.count, 3)
			connection.commit()
		finally:
			connection.close()

		observer = sqlite3.connect(path)
		try:
			assert_eq(observer.execute("SELECT * FROM update_log").fetchall(), [])
		finally:
			observer.close()


def test_update_writes_only_given_columns():
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
		connection = Connection.open(path)
		connection.begin()
		try:
			registry = Registry()
			registry.model(Record)
			registry.codec(TokenCodec())
			store = Store(connection, registry)
			model = store.create(Record, **record_values())
			store.update(model, name=model.name)
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


def test_deletes_model_and_reports_missing_lookup():
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path)
		connection = Connection.open(path)
		connection.begin()
		try:
			registry = Registry()
			registry.model(Record)
			registry.codec(TokenCodec())
			store = Store(connection, registry)
			model = store.create(Record, **record_values())
			store.delete(model)

			with assert_raises(NotFoundError) as raised:
				store.find_one(Record, model.id)
			exception = raised.exception
			assert_eq(exception.model_type, Record)
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

		connection = Connection.open(path)
		connection.begin()
		registry = Registry()
		registry.model(Record)
		registry.codec(TokenCodec())
		try:
			with assert_raises(DatabaseError):
				Store(connection, registry).find_all(Record)
		finally:
			connection.close()


def test_round_trips_models_with_value_types_declared_later():
	class Badge(Model):
		table = "badges"
		label: Label

	class Label:
		def __init__(self, text: str):
			self.text = text

	class LabelCodec(Codec[Label]):
		converts = Label

		def encode(self, value: Label) -> Scalar:
			return value.text

		def decode(self, value: Scalar) -> Label:
			return Label(str(value))

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
		connection = Connection.open(path)
		connection.begin()
		try:
			registry = Registry()
			registry.model(Badge)
			registry.codec(LabelCodec())
			created = Store(connection, registry).create(Badge, label=Label("new"))
			connection.commit()
		finally:
			connection.close()

		second_connection = Connection.open(path)
		second_connection.begin()
		try:
			registry = Registry()
			registry.model(Badge)
			registry.codec(LabelCodec())
			found = Store(second_connection, registry).find_one(Badge, created.id)
		finally:
			second_connection.close()

		assert_is_not(found, created)
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
		connection = Connection.open(path)
		connection.begin()
		try:
			registry = Registry()
			registry.model(OddRecord)
			store = Store(connection, registry)
			model = store.create(OddRecord, select="value")

			assert_eq(store.find_one(OddRecord, model.id).id, model.id)
			assert_eq(model.select, "value")

			store.update(model, select="changed")
			assert_eq(store.find_one(OddRecord, model.id).select, "changed")
		finally:
			connection.close()


def test_rejects_unregistered_models():
	class Other(Model):
		table = "others"

	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			with assert_raises(ModelError):
				store.find_all(Other)
			with assert_raises(ModelError):
				store.create(Other)
		finally:
			connection.close()


def open_record_store(directory: str):
	path = Path(directory, "app.sqlite")
	create_database(path)
	connection = Connection.open(path)
	connection.begin()
	registry = Registry()
	registry.model(Record)
	registry.codec(TokenCodec())
	return connection, Store(connection, registry)


def test_reads_return_distinct_models():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			created = store.create(Record, **record_values())
			first = store.find_one(Record, created.id)
			second = store.find_one(Record, created.id)

			assert_is_not(first, second)
			assert_eq(first.name, second.name)
			assert_eq(first.count, second.count)
		finally:
			connection.close()


def test_create_returns_a_stored_model():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			created = store.create(Record, **record_values())

			assert_is_instance(created.id, UUID)
			assert_eq(created.created_at.tzinfo, UTC)
			found = store.find_one(Record, created.id)
			assert_eq(found.created_at, created.created_at)
			assert_eq(found.name, created.name)
			assert_eq(found.token.value, "secret")
		finally:
			connection.close()


def test_update_sets_values_on_the_model():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			model = store.create(Record, **record_values())
			holders = [model]

			store.update(model, name="Revised", note="Short")

			assert_eq(model.name, "Revised")
			assert_eq(holders[0].note, "Short")
			found = store.find_one(Record, model.id)
			assert_eq(found.name, "Revised")
			assert_eq(found.note, "Short")
		finally:
			connection.close()


def test_update_and_delete_on_a_constructed_model_raise_not_found():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			model = Record(**record_values())

			with assert_raises(NotFoundError) as updated:
				store.update(model, name="Revised")
			with assert_raises(NotFoundError) as deleted:
				store.delete(model)

			for raised in (updated, deleted):
				exception = raised.exception
				assert_eq(exception.model_type, Record)
				assert_eq(exception.id, model.id)
			assert_eq(model.name, "Intro")
		finally:
			connection.close()


def test_update_and_delete_after_the_row_is_deleted_raise_not_found():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			created = store.create(Record, **record_values())
			first = store.find_one(Record, created.id)
			second = store.find_one(Record, created.id)
			store.delete(first)

			with assert_raises(NotFoundError):
				store.update(second, name="Revised")
			with assert_raises(NotFoundError):
				store.delete(second)
			assert_eq(second.name, "Intro")
		finally:
			connection.close()


def test_deleting_twice_raises_not_found():
	with TemporaryDirectory() as directory:
		connection, store = open_record_store(directory)
		try:
			model = store.create(Record, **record_values())
			store.delete(model)

			with assert_raises(NotFoundError):
				store.delete(model)
		finally:
			connection.close()


class Post(Model):
	table = "posts"

	title: str


def open_post_store(directory: str):
	path = Path(directory, "app.sqlite")
	create_database(
		path,
		"CREATE TABLE posts (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL)",
	)
	connection = Connection.open(path)
	transaction = Transaction(connection)
	registry = Registry()
	registry.model(Post)
	return connection, transaction, Store(transaction, registry)


def test_store_over_ended_transaction_refuses_writes():
	with TemporaryDirectory() as directory:
		connection, transaction, store = open_post_store(directory)
		try:
			transaction.commit()

			with assert_raises(RuntimeError) as raised:
				store.create(Post, title="Intro")
			assert_is(type(raised.exception), RuntimeError)
		finally:
			connection.close()


def test_store_over_ended_transaction_refuses_reads():
	with TemporaryDirectory() as directory:
		connection, transaction, store = open_post_store(directory)
		try:
			transaction.commit()

			with assert_raises(RuntimeError) as raised:
				store.find_all(Post)
			assert_is(type(raised.exception), RuntimeError)
		finally:
			connection.close()


JSON_SCHEMA = """
CREATE TABLE posts (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	metadata TEXT NOT NULL,
	tag_ids TEXT
);
"""


def test_round_trips_a_json_object():
	class Post(Model):
		table = "posts"
		metadata: JSON[dict[str, Any]]

	registry = Registry()
	registry.model(Post)
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, JSON_SCHEMA)
		connection = Connection.open(path)
		connection.begin()
		try:
			store = Store(connection, registry)
			created = store.create(Post, metadata={"summary": "Intro", "pinned": True})

			found = store.find_one(Post, created.id)
		finally:
			connection.close()

	assert_eq(found.metadata, {"summary": "Intro", "pinned": True})


def test_stores_null_in_a_nullable_json_column():
	class Post(Model):
		table = "posts"
		metadata: JSON[dict[str, Any]]
		tag_ids: JSON[list[int]] | None = None

	registry = Registry()
	registry.model(Post)
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, JSON_SCHEMA)
		connection = Connection.open(path)
		connection.begin()
		try:
			store = Store(connection, registry)
			created = store.create(Post, metadata={}, tag_ids=None)

			found = store.find_one(Post, created.id)
		finally:
			connection.close()

	assert_eq(found.tag_ids, None)


def test_refuses_to_store_a_value_that_is_not_json():
	class Post(Model):
		table = "posts"
		metadata: JSON[dict[str, Any]]

	registry = Registry()
	registry.model(Post)
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, JSON_SCHEMA)
		connection = Connection.open(path)
		connection.begin()
		try:
			store = Store(connection, registry)

			with assert_raises(ModelError):
				store.create(Post, metadata={"tags": {"intro"}})
		finally:
			connection.close()


def test_stored_json_of_the_wrong_type_is_database_error():
	class Post(Model):
		table = "posts"
		metadata: JSON[dict[str, Any]]

	registry = Registry()
	registry.model(Post)
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(
			path,
			JSON_SCHEMA
			+ f"""
			INSERT INTO posts VALUES (
				'{uuid4()}',
				'2025-01-02T03:04:05.000006Z',
				'[1]',
				NULL
			);
			""",
		)
		connection = Connection.open(path)
		connection.begin()
		try:
			store = Store(connection, registry)

			with assert_raises(DatabaseError):
				store.find_all(Post)
		finally:
			connection.close()


def test_refuses_to_store_an_unsupported_column_type():
	class Post(Model):
		table = "posts"
		metadata: list[str]

	registry = Registry()
	registry.model(Post)
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		create_database(path, JSON_SCHEMA)
		connection = Connection.open(path)
		connection.begin()
		try:
			store = Store(connection, registry)

			with assert_raises(ModelError):
				store.create(Post, metadata=["intro"])
		finally:
			connection.close()
