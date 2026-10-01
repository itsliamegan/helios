from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises

from helios.database import (
	Config,
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


class Fixture:
	def __init__(self, store: Store):
		self.ada = store.create(User, name="Ada")
		self.bo = store.create(User, name="Bo")
		self.cy = store.create(User, name="Cy")
		self.ideas = store.create(Board, title="Ideas", creator_id=self.ada.id)
		self.plans = store.create(Board, title="Plans", creator_id=self.bo.id)
		self.secret = store.create(Board, title="Secret", creator_id=self.cy.id)
		store.create(Share, board_id=self.plans.id, user_id=self.ada.id)
		self.sketch = store.create(Pin, title="Sketch")
		self.photo = store.create(Pin, title="Photo")
		self.note = store.create(Pin, title="Note")
		store.create(Document, pin_id=self.sketch.id, body="Lines")
		self.sketch_on_ideas = self.place(store, self.sketch, self.ideas, 0)
		self.photo_on_ideas = self.place(store, self.photo, self.ideas, 1)
		self.sketch_on_plans = self.place(store, self.sketch, self.plans, 1)
		self.note_on_plans = self.place(store, self.note, self.plans, 0)
		self.sketch_on_secret = self.place(store, self.sketch, self.secret, 0)
		self.photo_on_secret = self.place(store, self.photo, self.secret, 1)

	def place(self, store: Store, pin: Pin, board: Board, position: int) -> Placement:
		return store.create(
			Placement,
			pin_id=pin.id,
			board_id=board.id,
			position=position,
		)


def titles(models: list[Board] | list[Pin]) -> set[str]:
	return {model.title for model in models}


def ids(models: list[Placement] | list[Invite]) -> set[UUID]:
	return {model.id for model in models}


def test_filters_through_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)

		found = store.query(Placement).where({"board.title": "Plans"}).all()

		assert_eq(
			ids(found),
			{fixture.sketch_on_plans.id, fixture.note_on_plans.id},
		)


def test_filters_through_has_many_and_has_one():
	with open_store() as store:
		fixture = Fixture(store)

		boards = store.query(Board).where({"placements.pin_id": fixture.note.id})
		pins = store.query(Pin).where({"document.body": "Lines"})

		assert_eq(titles(boards.all()), {"Plans"})
		assert_eq(titles(pins.all()), {"Sketch"})


def test_filters_through_nested_paths():
	with open_store() as store:
		Fixture(store)

		found = store.query(Pin).where({"placements.board.title": "Secret"}).all()

		assert_eq(titles(found), {"Sketch", "Photo"})


def test_applies_access_rules():
	with open_store() as store:
		fixture = Fixture(store)
		user = fixture.ada.id

		boards = store.query(Board).where_any(
			{"creator_id": user},
			{"shares.user_id": user},
		)
		placements = (
			store.query(Placement)
			.where({"pin_id": fixture.sketch.id})
			.where_any({"board.creator_id": user}, {"board.shares.user_id": user})
		)

		assert_eq(titles(boards.all()), {"Ideas", "Plans"})
		assert_eq(
			ids(placements.all()),
			{fixture.sketch_on_ideas.id, fixture.sketch_on_plans.id},
		)


def test_keys_under_one_path_apply_to_the_same_related_row():
	with open_store() as store:
		fixture = Fixture(store)
		conditions = {"placements.position": 0, "placements.pin_id": fixture.photo.id}

		together = store.query(Board).where(conditions).all()
		apart = (
			store.query(Board)
			.where({"placements.position": 0})
			.where({"placements.pin_id": fixture.photo.id})
			.all()
		)
		grouped = (
			store.query(Board)
			.where_any({"placements.position": 0})
			.where_any({"placements.pin_id": fixture.photo.id})
			.all()
		)

		assert_eq(together, [])
		assert_eq(titles(apart), {"Ideas", "Secret"})
		assert_eq(titles(grouped), {"Ideas", "Secret"})


def test_nests_paths_under_a_shared_relationship():
	with open_store() as store:
		fixture = Fixture(store)

		found = (
			store.query(Pin)
			.where(
				{
					"placements.position": 0,
					"placements.board.creator_id": fixture.bo.id,
				}
			)
			.all()
		)

		assert_eq(titles(found), {"Note"})


def test_where_not_is_the_exact_complement_of_a_path():
	with open_store() as store:
		fixture = Fixture(store)
		invited = store.create(Invite, target_id=fixture.ada.id)
		other = store.create(Invite, target_id=fixture.bo.id)
		open_invite = store.create(Invite)

		kept = store.query(Invite).where({"target.name": "Ada"}).all()
		dropped = store.query(Invite).where_not({"target.name": "Ada"}).all()

		assert_eq(ids(kept), {invited.id})
		assert_eq(ids(dropped), {other.id, open_invite.id})


def test_follows_a_path_through_the_same_table_twice():
	with open_store() as store:
		fixture = Fixture(store)

		found = (
			store.query(Placement)
			.where({"board.placements.pin_id": fixture.note.id})
			.all()
		)

		assert_eq(
			ids(found),
			{fixture.sketch_on_plans.id, fixture.note_on_plans.id},
		)


def test_count_by_and_exists_respect_paths():
	with open_store() as store:
		fixture = Fixture(store)
		shared = store.query(Placement).where({"board.shares.user_id": fixture.ada.id})

		assert_eq(
			shared.count_by("pin_id"),
			{fixture.sketch.id: 1, fixture.note.id: 1},
		)
		assert_eq(shared.exists(), True)
		assert_eq(
			store.query(Board).where({"shares.user_id": fixture.cy.id}).exists(),
			False,
		)


def test_rejects_invalid_paths():
	with open_store() as store:
		cases = [
			("pin_id.title", "where Placement.pin_id is not a relationship"),
			("board", "where Placement.board is not a column"),
			("board.titel", "where Board.titel is not a column"),
			("board..title", "which is not of the form 'name' or 'name operator'"),
		]
		for key, detail in cases:
			with assert_raises(ModelError) as raised:
				store.query(Placement).where({key: "Ideas"})
			assert_eq(
				str(raised.exception), f"Query on Placement has {key!r}, {detail}"
			)


def test_checks_values_against_the_final_attribute():
	with open_store() as store, assert_raises(ModelError):
		store.query(Placement).where({"board.title": 1})
