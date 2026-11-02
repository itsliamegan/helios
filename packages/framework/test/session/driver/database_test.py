from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_not_none,
	assert_raises,
	assert_that,
)

from helios.database import Database
from helios.database.registry import Registry
from helios.session.command import MIGRATION_FILE
from helios.session.driver.database import Driver, Record
from helios.session.driver.database.items import Items
from helios.session.driver.database.token import Token
from helios.session.session import Session


def create_database(path: Path) -> Database:
	connection = sqlite3.connect(path, autocommit=True)
	try:
		connection.executescript(MIGRATION_FILE.read_text())
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


def test_driver_reads_a_written_session():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		last_active_at = datetime(2026, 10, 12, tzinfo=UTC)
		with database.store() as store:
			Driver(store).write(
				Session("visitor-token", {"message": "Hello"}, last_active_at)
			)

		with database.store() as store:
			session = assert_not_none(Driver(store).read("visitor-token"))

	assert_eq(session.items, {"message": "Hello"})
	assert_eq(session.last_active_at, last_active_at)
	assert_that(session.stored)


def test_driver_replaces_a_written_session():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		last_active_at = datetime(2026, 10, 12, tzinfo=UTC)
		with database.store() as store:
			driver = Driver(store)
			driver.write(Session("visitor-token", {"message": "Hello"}))
			driver.write(
				Session("visitor-token", {"message": "Changed"}, last_active_at)
			)

			session = assert_not_none(driver.read("visitor-token"))
			records = store.find_all(Record)

	assert_eq(session.items, {"message": "Changed"})
	assert_eq(session.last_active_at, last_active_at)
	assert_eq(len(records), 1)


def test_driver_destroys_a_session():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		with database.store() as store:
			driver = Driver(store)
			driver.write(Session("visitor-token", {"message": "Hello"}))

			driver.destroy("visitor-token")

			assert_is(driver.read("visitor-token"), None)


def test_driver_destroying_an_unknown_token_succeeds():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		with database.store() as store:
			driver = Driver(store)

			driver.destroy("unknown-token")

			assert_is(driver.read("unknown-token"), None)


def test_driver_purges_sessions_last_active_before_the_cutoff():
	with TemporaryDirectory() as directory:
		database = create_database(Path(directory, "app.sqlite"))
		cutoff = datetime(2026, 10, 12, tzinfo=UTC)
		with database.store() as store:
			driver = Driver(store)
			driver.write(
				Session(
					"expired-token",
					last_active_at=cutoff - timedelta(microseconds=1),
				)
			)
			driver.write(Session("active-token", last_active_at=cutoff))

			driver.purge(cutoff)

			assert_is(driver.read("expired-token"), None)
			assert_not_none(driver.read("active-token"))
