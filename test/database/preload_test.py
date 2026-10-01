from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import (
	Config,
	DatabaseError,
	Model,
	ModelError,
	Store,
	belongs_to,
	has_many,
	has_one,
)
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


MODELS: list[type[Model]] = [User, Board, Pin, Placement, Share, Document, Invite]

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
def open_store(
	model_types: list[type[Model]] = MODELS,
	rows: str = "",
) -> Iterator[Store]:
	with TemporaryDirectory() as directory:
		path = Path(directory, "app.sqlite")
		raw = sqlite3.connect(path, autocommit=True)
		raw.executescript(SCHEMA)
		raw.execute("PRAGMA foreign_keys = OFF")
		raw.executescript(rows)
		raw.close()
		with connect(Config(path)) as connection:
			connection.begin()
			yield Store(connection, model_types)


@contextmanager
def recording(store: Store) -> Iterator[list[str]]:
	statements: list[str] = []
	store.connection.connection.set_trace_callback(statements.append)
	try:
		yield statements
	finally:
		store.connection.connection.set_trace_callback(None)


def selects(statements: list[str], table: str) -> int:
	prefix = 'SELECT "id", "created_at"'
	return sum(
		1
		for statement in statements
		if statement.startswith(prefix)
		and f'FROM "{table}"' in statement.split(" WHERE ")[0]
	)


class Fixture:
	def __init__(self, store: Store):
		self.ada = store.create(User, name="Ada")
		self.ideas = store.create(Board, title="Ideas", creator_id=self.ada.id)
		self.empty = store.create(Board, title="Empty", creator_id=self.ada.id)
		self.sketch = store.create(Pin, title="Sketch")
		self.photo = store.create(Pin, title="Photo")
		self.document = store.create(Document, pin_id=self.sketch.id, body="Lines")
		self.first = self.place(store, self.sketch, 0)
		self.second = self.place(store, self.photo, 1)
		self.third = self.place(store, self.sketch, 2)

	def place(self, store: Store, pin: Pin, position: int) -> Placement:
		return store.create(
			Placement,
			pin_id=pin.id,
			board_id=self.ideas.id,
			position=position,
		)


def by_position(placements: list[Placement]) -> list[int]:
	return sorted(placement.position for placement in placements)


def test_loads_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)
		invited = store.create(Invite, target_id=fixture.ada.id)
		unaddressed = store.create(Invite)

		store.preload([fixture.first, fixture.second], "pin")
		store.preload([invited, unaddressed], "target")

		assert_eq(fixture.first.pin.id, fixture.sketch.id)
		assert_eq(fixture.second.pin.title, "Photo")
		assert_that(invited.target is not None and invited.target.name == "Ada")
		assert_that(unaddressed.target is None)


def test_loads_has_many():
	with open_store() as store:
		fixture = Fixture(store)

		store.preload([fixture.ideas, fixture.empty], "placements")

		assert_eq(by_position(fixture.ideas.placements), [0, 1, 2])
		assert_eq(fixture.empty.placements, [])


def test_loads_has_one():
	with open_store() as store:
		fixture = Fixture(store)

		store.preload([fixture.sketch, fixture.photo], "document")

		document = fixture.sketch.document
		assert document is not None
		assert_eq(document.body, "Lines")
		assert_that(fixture.photo.document is None)


def test_loads_nested_paths_and_runs_shared_prefixes_once():
	with open_store() as store:
		fixture = Fixture(store)
		board = store.find_one(Board, fixture.ideas.id)

		with recording(store) as statements:
			store.preload(board, "placements.pin", "placements.board")

		assert_eq(selects(statements, "placements"), 1)
		assert_eq(
			sorted(placement.pin.title for placement in board.placements),
			["Photo", "Sketch", "Sketch"],
		)
		assert_eq(
			{placement.board.id for placement in board.placements},
			{board.id},
		)


def test_reuses_loaded_relationships():
	with open_store() as store:
		fixture = Fixture(store)
		board = store.find_one(Board, fixture.ideas.id)
		store.preload(board, "placements")
		placements = board.placements

		with recording(store) as statements:
			store.preload(board, "placements.pin")

		assert_that(board.placements is placements)
		assert_eq(selects(statements, "placements"), 0)
		assert_eq(selects(statements, "pins"), 1)
		assert_eq(
			sorted(placement.pin.title for placement in placements),
			["Photo", "Sketch", "Sketch"],
		)


def test_shares_one_object_per_row():
	with open_store() as store:
		fixture = Fixture(store)
		placements = store.query(Placement).where({"pin_id": fixture.sketch.id}).all()

		store.preload(placements, "pin")

		assert_eq(len(placements), 2)
		assert_that(placements[0].pin is placements[1].pin)


def test_splits_large_id_sets_into_batches():
	with open_store() as store:
		fixture = Fixture(store)
		for position in range(3, 8):
			fixture.place(store, store.create(Pin, title=f"Pin {position}"), position)
		placements = store.find_all(Placement)
		store.connection.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 2)

		with recording(store) as statements:
			store.preload(placements, "pin")

		assert_eq(selects(statements, "pins"), 4)
		assert_eq(
			{placement.pin.id for placement in placements},
			{placement.pin_id for placement in placements},
		)


def test_runs_no_query_without_ids():
	with open_store() as store:
		invites = [store.create(Invite), store.create(Invite)]

		with recording(store) as statements:
			store.preload(invites, "target")

		assert_eq(statements, [])
		assert_that(all(invite.target is None for invite in invites))


def test_update_unloads_a_changed_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)
		store.preload([fixture.first, fixture.second], "pin")

		store.update(fixture.first, pin_id=fixture.photo.id)
		store.update(fixture.second, pin_id=fixture.photo.id, position=4)

		with assert_raises(ModelError):
			_ = fixture.first.pin
		assert_eq(fixture.second.pin.title, "Photo")


def test_loaded_lists_are_snapshots():
	with open_store() as store:
		fixture = Fixture(store)
		store.preload([fixture.ideas, fixture.empty], "placements")

		fixture.place(store, fixture.photo, 3)
		store.delete(fixture.second)
		store.update(fixture.third, board_id=fixture.empty.id)

		assert_eq(by_position(fixture.ideas.placements), [0, 1, 2])
		assert_eq(fixture.empty.placements, [])


def test_rejects_invalid_arguments_before_any_query():
	with open_store() as store:
		fixture = Fixture(store)
		constructed = Placement(
			pin_id=fixture.sketch.id, board_id=fixture.ideas.id, position=9
		)
		cases = [
			(
				lambda: store.preload(fixture.first),
				"store.preload requires at least one path",
			),
			(
				lambda: store.preload(fixture.first, "pin.titel"),
				(
					"store.preload on Placement has 'pin.titel', "
					"where Pin.titel is not a relationship"
				),
			),
			(
				lambda: store.preload(fixture.first, "pin."),
				"store.preload on Placement has 'pin.', which is not a relationship path",
			),
			(
				lambda: store.preload([fixture.first, fixture.sketch], "pin"),
				"store.preload takes models of one model type, got Placement and Pin",
			),
			(
				lambda: store.preload("placements", "pin"),  # ty: ignore[invalid-argument-type]
				"store.preload takes a model or a list of models, got str",
			),
			(
				lambda: store.preload([fixture.first, constructed], "pin"),
				(
					"store.preload takes stored models, "
					f"and {constructed!r} was built with the constructor"
				),
			),
		]

		with recording(store) as statements:
			for preload, message in cases:
				with assert_raises(ModelError) as raised:
					preload()
				assert_eq(str(raised.exception), message)
			store.preload([], "pin")

		assert_eq(statements, [])


def test_rejects_several_has_one_rows():
	with open_store() as store:
		fixture = Fixture(store)
		store.create(Document, pin_id=fixture.sketch.id, body="Shading")

		with assert_raises(DatabaseError) as raised:
			store.preload(fixture.sketch, "document")

		assert_eq(
			str(raised.exception),
			f"Pin.document has several Document rows for Pin {fixture.sketch.id}",
		)


def test_rejects_a_dangling_belongs_to():
	user_id, board_id, placement_id, pin_id = uuid4(), uuid4(), uuid4(), uuid4()
	created = "2025-01-02T03:04:05.000000Z"
	rows = f"""
	INSERT INTO users VALUES ('{user_id}', '{created}', 'Ada');
	INSERT INTO boards VALUES ('{board_id}', '{created}', 'Ideas', '{user_id}');
	INSERT INTO placements
	VALUES ('{placement_id}', '{created}', '{pin_id}', '{board_id}', 0);
	"""
	with open_store(rows=rows) as store:
		placement = store.find_one(Placement, placement_id)

		with assert_raises(DatabaseError) as raised:
			store.preload(placement, "pin")

		assert_eq(
			str(raised.exception),
			f"Placement.pin refers to Pin {pin_id}, which does not exist",
		)


def test_rejects_an_unregistered_target():
	with open_store([User, Board, Placement]) as store:
		user = store.create(User, name="Ada")
		board = store.create(Board, title="Ideas", creator_id=user.id)

		with assert_raises(ModelError):
			store.preload(board, "placements.pin")
