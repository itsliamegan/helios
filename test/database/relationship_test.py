from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Config, Model, ModelError, Store
from helios.database.relationship import belongs_to, has_many, has_one
from helios.database.sqlite import connect


class User(Model):
	table = "users"

	name: str


class Board(Model):
	table = "boards"

	title: str
	creator_id: UUID
	creator: User = belongs_to("creator_id")
	placements: list[Placement] = has_many("board_id")
	shares: list[Share] = has_many("board_id")


class Pin(Model):
	table = "pins"

	title: str
	placements: list[Placement] = has_many("pin_id")
	document: Document | None = has_one("pin_id")


class Placement(Model):
	table = "placements"

	pin_id: UUID
	pin: Pin = belongs_to("pin_id")
	board_id: UUID
	board: Board = belongs_to("board_id")
	position: int


class Share(Model):
	table = "shares"

	board_id: UUID
	board: Board = belongs_to("board_id")
	user_id: UUID
	user: User = belongs_to("user_id")


class Document(Model):
	table = "documents"

	pin_id: UUID
	pin: Pin = belongs_to("pin_id")
	body: str


class Invite(Model):
	table = "invites"

	target_id: UUID | None = None
	target: User | None = belongs_to("target_id")


MODELS = [User, Board, Pin, Placement, Share, Document, Invite]

SCHEMA = """
CREATE TABLE users (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL
);
CREATE TABLE boards (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	title TEXT NOT NULL,
	creator_id TEXT NOT NULL REFERENCES users (id)
);
CREATE TABLE pins (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	title TEXT NOT NULL
);
CREATE TABLE placements (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	pin_id TEXT NOT NULL REFERENCES pins (id),
	board_id TEXT NOT NULL REFERENCES boards (id),
	position INTEGER NOT NULL
);
CREATE TABLE shares (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	board_id TEXT NOT NULL REFERENCES boards (id),
	user_id TEXT NOT NULL REFERENCES users (id)
);
CREATE TABLE documents (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	pin_id TEXT NOT NULL REFERENCES pins (id),
	body TEXT NOT NULL
);
CREATE TABLE invites (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	target_id TEXT REFERENCES users (id)
);
"""


@contextmanager
def open_store() -> Iterator[Store]:
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		raw = sqlite3.connect(path, autocommit=True)
		raw.executescript(SCHEMA)
		raw.close()
		with connect(Config(path)) as connection:
			connection.begin()
			yield Store(connection, MODELS)


def test_relationships_are_not_constructor_parameters():
	user = User(name="Ada")
	board = Board(title="Ideas", creator_id=user.id)
	pin = Pin(title="Sketch")

	with assert_raises(TypeError):
		Board(
			title="Ideas",
			creator_id=user.id,
			creator=user,  # ty: ignore[unknown-argument]
		)
	with assert_raises(TypeError):
		Board(
			title="Ideas",
			creator_id=user.id,
			placements=[],  # ty: ignore[unknown-argument]
		)
	with assert_raises(TypeError):
		Pin(title="Sketch", document=None)  # ty: ignore[unknown-argument]
	assert_eq(board.creator_id, user.id)
	assert_eq(pin.title, "Sketch")


def test_rejects_a_belongs_to_naming_a_missing_or_non_uuid_column():
	with assert_raises(ModelError) as missing:

		class MissingId(Model):
			pin_id: UUID
			pin: Pin = belongs_to("pin_ide")

	with assert_raises(ModelError) as not_uuid:

		class TextId(Model):
			title: str
			pin: Pin = belongs_to("title")

	assert_eq(
		str(missing.exception),
		"MissingId.pin: belongs_to names 'pin_ide', which is not a column",
	)
	assert_eq(
		str(not_uuid.exception),
		"TextId.pin: belongs_to names 'title', which does not hold a UUID",
	)


def test_rejects_wrong_annotations():
	with assert_raises(ModelError) as belongs:

		class Mark(Model):
			pin_id: UUID
			pin: str = belongs_to("pin_id")

	with assert_raises(ModelError) as many:

		class Shelf(Model):
			placements: Placement = has_many("board_id")

	with assert_raises(ModelError) as one:

		class Card(Model):
			document: list[str] = has_one("pin_id")

	with assert_raises(ModelError) as not_nullable:

		class Folder(Model):
			document: Document = has_one("pin_id")

	assert_eq(str(belongs.exception), "Mark.pin: expected a model, got <class 'str'>")
	assert_eq(
		str(many.exception),
		f"Shelf.placements: expected list[<model>], got {Placement!r}",
	)
	assert_eq(
		str(one.exception),
		"Card.document: expected <model> | None, got list[str]",
	)
	assert_eq(
		str(not_nullable.exception),
		f"Folder.document: expected <model> | None, got {Document!r}",
	)


def test_checks_forward_referenced_annotations_on_first_use():
	class Note(Model):
		author_id: UUID
		author: list[Author] = belongs_to("author_id")

	class Author(Model):
		name: str

	with assert_raises(ModelError):
		_ = Note.relationships["author"].target


def test_resolves_targets_declared_after_the_model():
	assert_that(Board.relationships["placements"].target is Placement)
	assert_that(Board.relationships["shares"].target is Share)
	assert_that(Pin.relationships["document"].target is Document)


def test_rejects_a_nullability_mismatch_on_first_use():
	class Loose(Model):
		user_id: UUID
		user: User | None = belongs_to("user_id")

	class Strict(Model):
		user_id: UUID | None = None
		user: User = belongs_to("user_id")

	with assert_raises(ModelError) as loose:
		_ = Loose.relationships["user"].target
	with assert_raises(ModelError) as strict:
		_ = Strict.relationships["user"].target

	assert_eq(
		str(loose.exception),
		"Loose.user: annotation must include None exactly when "
		"Loose.user_id is nullable",
	)
	assert_eq(
		str(strict.exception),
		"Strict.user: annotation must include None exactly when "
		"Strict.user_id is nullable",
	)
	assert_that(Invite.relationships["target"].target is User)


def test_rejects_a_target_column_that_is_missing_or_not_a_uuid():
	class Wall(Model):
		placements: list[Placement] = has_many("board_ide")
		positioned: list[Placement] = has_many("position")
		document: Document | None = has_one("body")

	cases = [
		("placements", "Wall.placements: Placement.board_ide does not hold a UUID"),
		("positioned", "Wall.positioned: Placement.position does not hold a UUID"),
		("document", "Wall.document: Document.body does not hold a UUID"),
	]
	for name, message in cases:
		with assert_raises(ModelError) as raised:
			_ = Wall.relationships[name].target
		assert_eq(str(raised.exception), message)


def test_reading_an_unloaded_relationship_raises():
	with open_store() as store:
		user = store.create(User, name="Ada")
		board = store.create(Board, title="Ideas", creator_id=user.id)
		stored = store.find_one(Board, board.id)
		constructed = Board(title="Ideas", creator_id=user.id)

		with assert_raises(ModelError) as from_store:
			_ = stored.placements
		with assert_raises(ModelError) as from_constructor:
			_ = constructed.creator

		assert_eq(
			str(from_store.exception),
			"Board.placements is not loaded; "
			"load it with store.preload(models, 'placements')",
		)
		assert_eq(
			str(from_constructor.exception),
			"Board.creator is not loaded, "
			"and a model built with the constructor cannot be loaded",
		)


def test_assigning_a_relationship_raises():
	placement = Placement(pin_id=uuid4(), board_id=uuid4(), position=0)
	board = Board(title="Ideas", creator_id=uuid4())

	with assert_raises(AttributeError) as belongs:
		placement.pin = Pin(title="Sketch")
	with assert_raises(AttributeError) as many:
		board.placements = []

	assert_eq(
		str(belongs.exception),
		"Placement.pin is read-only; use store.update on Placement.pin_id",
	)
	assert_eq(str(many.exception), "Board.placements is read-only")


def test_relationships_are_not_columns():
	with open_store() as store:
		user = store.create(User, name="Ada")
		board = store.create(Board, title="Ideas", creator_id=user.id)

		with assert_raises(ModelError) as raised:
			Board.column("creator")
		with assert_raises(ModelError):
			store.query(Board).order_by("creator")
		with assert_raises(ModelError):
			store.query(Board).count_by("placements")
		with assert_raises(ModelError):
			store.update(board, creator=user)
		with assert_raises(ModelError):
			store.find_by(Board, creator=user)

		assert_eq(
			str(raised.exception),
			"Board.creator is a relationship, not a column",
		)


def test_rejects_relationships_with_reserved_names():
	with assert_raises(ModelError):

		class Shadow(Model):
			id: User = belongs_to("user_id")
			user_id: UUID

	with assert_raises(ModelError):

		class Meta(Model):
			relationships: list[Placement] = has_many(  # ty: ignore[invalid-attribute-override]
				"board_id"
			)
