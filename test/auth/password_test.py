from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_not, assert_raises, assert_that

from helios.auth.password import Digest, Password
from helios.database import Config, Model, Store, attribute
from helios.database.sqlite import connect

Digest.method = "pbkdf2:sha256:1"


def test_creates_and_matches_password():
	password = Password.from_plaintext("correct")

	assert_that(password.matches("correct"))
	assert_not(password.matches("incorrect"))


def test_redacts_password_representation():
	password = Password.from_plaintext("secret")
	encoded = Password.encode(password)

	assert_that(encoded not in repr(password))
	assert_that("secret" not in repr(password))


def test_round_trips_password_attrs():
	class Account(Model):
		table = "accounts"

		password = attribute(Password)
		backup_password = attribute(Password, nullable=True)

	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		raw = sqlite3.connect(path, autocommit=True)
		raw.execute(
			"""
			CREATE TABLE accounts (
				id TEXT PRIMARY KEY,
				created_at TEXT NOT NULL,
				password TEXT NOT NULL,
				backup_password TEXT
			)
			"""
		)
		raw.close()
		connection = connect(Config(path))
		connection.begin()
		store = Store(connection, [Account])
		created = store.create(
			Account,
			password=Password.from_plaintext("secret"),
		)
		connection.commit()
		connection.close()

		connection = connect(Config(path))
		connection.begin()
		try:
			found = Store(connection, [Account]).find_one(Account, created.id)
			password: Password = found.password
			backup_password: Password | None = found.backup_password

			assert_that(password.matches("secret"))
			assert_that(backup_password is None)
		finally:
			connection.close()


def test_rejects_malformed_encoded_password():
	with assert_raises(TypeError):
		Password.decode(42)


def test_generates_and_checks_digest():
	digest = Digest.generate("secret")

	assert_that(digest.matches("secret"))
	assert_not(digest.matches("incorrect"))


def test_generates_salted_digests():
	first = Digest.generate("secret")
	second = Digest.generate("secret")

	assert_that(first.encode() != second.encode())


def test_decodes_digest_without_rehashing():
	generated = Digest.generate("secret")
	encoded = generated.encode()

	decoded = Digest.decode(encoded)

	assert_eq(decoded.encode(), encoded)
	assert_that(decoded.matches("secret"))


def test_rejects_malformed_digest_representation():
	with assert_raises(TypeError):
		Digest.decode(42)


def test_redacts_digest_representation():
	digest = Digest.generate("secret")

	assert_that(digest.encode() not in repr(digest))
	assert_that("secret" not in repr(digest))
