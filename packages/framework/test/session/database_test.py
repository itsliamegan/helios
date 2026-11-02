from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

from helios.database import Database
from helios.database.registry import Registry
from helios.session.database import Items, Record, SCHEMA, Token


def create_database(path: Path) -> Database:
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.executescript(SCHEMA)
	finally:
		connection.close()
	return Database(path, Registry([Record]))


def test_round_trips_a_record():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		last_active_at = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
		with database.store() as store:
			created = store.create(
				Record,
				token=Token.from_plaintext("visitor-token"),
				items=Items({"_user_id": "alice", "_flash": {"notice": "Saved"}}),
				last_active_at=last_active_at,
			)

		with database.store() as store:
			found = store.find_one(Record, created.id)

	assert_eq(found.token, Token.from_plaintext("visitor-token"))
	assert_eq(found.items, Items({"_user_id": "alice", "_flash": {"notice": "Saved"}}))
	assert_eq(found.last_active_at, last_active_at)


def test_finds_a_record_by_its_token():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		with database.store() as store:
			for token in ["first-token", "second-token"]:
				store.create(
					Record,
					token=Token.from_plaintext(token),
					items=Items({"token": token}),
					last_active_at=datetime(2026, 10, 12, tzinfo=UTC),
				)

			found = store.find_by(Record, token=Token.from_plaintext("second-token"))

	assert_eq([record.items for record in found], [Items({"token": "second-token"})])


def test_items_refuse_json_that_is_not_an_object():
	with assert_raises(TypeError):
		Items.Codec().decode('["notice"]')
