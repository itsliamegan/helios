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


class Author(Model):
	table = "authors"

	name: str
	profile: Profile | None = has_one("author_id")


class Post(Model):
	table = "posts"

	title: str
	author_id: UUID
	author: Author = belongs_to("author_id")
	taggings: list[Tagging] = has_many("post_id")
	comments: list[Comment] = has_many("post_id")


class Tag(Model):
	table = "tags"

	name: str
	taggings: list[Tagging] = has_many("tag_id")


class Tagging(Model):
	table = "taggings"

	post_id: UUID
	post: Post = belongs_to("post_id")
	tag_id: UUID
	tag: Tag = belongs_to("tag_id")
	position: int


class Comment(Model):
	table = "comments"

	post_id: UUID
	post: Post = belongs_to("post_id")
	author_id: UUID
	author: Author = belongs_to("author_id")


class Profile(Model):
	table = "profiles"

	author_id: UUID
	author: Author = belongs_to("author_id")
	bio: str


class Draft(Model):
	table = "drafts"

	reviewer_id: UUID | None = None
	reviewer: Author | None = belongs_to("reviewer_id")


MODELS: list[type[Model]] = [Author, Post, Tag, Tagging, Comment, Profile, Draft]

SCHEMA = """
CREATE TABLE authors (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL
);
CREATE TABLE posts (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	title TEXT NOT NULL,
	author_id TEXT NOT NULL REFERENCES authors (id)
);
CREATE TABLE tags (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL
);
CREATE TABLE taggings (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	post_id TEXT NOT NULL REFERENCES posts (id),
	tag_id TEXT NOT NULL REFERENCES tags (id),
	position INTEGER NOT NULL
);
CREATE TABLE comments (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	post_id TEXT NOT NULL REFERENCES posts (id),
	author_id TEXT NOT NULL REFERENCES authors (id)
);
CREATE TABLE profiles (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	author_id TEXT NOT NULL REFERENCES authors (id),
	bio TEXT NOT NULL
);
CREATE TABLE drafts (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	reviewer_id TEXT REFERENCES authors (id)
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
		self.ada = store.create(Author, name="Ada")
		self.bo = store.create(Author, name="Bo")
		self.profile = store.create(Profile, author_id=self.ada.id, bio="Writer")
		self.ideas = store.create(Post, title="Ideas", author_id=self.ada.id)
		self.empty = store.create(Post, title="Empty", author_id=self.ada.id)
		self.python = store.create(Tag, name="Python")
		self.rust = store.create(Tag, name="Rust")
		self.first = self.tag(store, self.python, 0)
		self.second = self.tag(store, self.rust, 1)
		self.third = self.tag(store, self.python, 2)

	def tag(self, store: Store, tag: Tag, position: int) -> Tagging:
		return store.create(
			Tagging,
			tag_id=tag.id,
			post_id=self.ideas.id,
			position=position,
		)


def by_position(taggings: list[Tagging]) -> list[int]:
	return sorted(tagging.position for tagging in taggings)


def test_loads_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)
		reviewed = store.create(Draft, reviewer_id=fixture.ada.id)
		unreviewed = store.create(Draft)

		store.load([fixture.first, fixture.second], "tag")
		store.load([reviewed, unreviewed], "reviewer")

		assert_eq(fixture.first.tag.id, fixture.python.id)
		assert_eq(fixture.second.tag.name, "Rust")
		assert_that(reviewed.reviewer is not None and reviewed.reviewer.name == "Ada")
		assert_that(unreviewed.reviewer is None)


def test_loads_has_many():
	with open_store() as store:
		fixture = Fixture(store)

		store.load([fixture.ideas, fixture.empty], "taggings")

		assert_eq(by_position(fixture.ideas.taggings), [0, 1, 2])
		assert_eq(fixture.empty.taggings, [])


def test_loads_has_one():
	with open_store() as store:
		fixture = Fixture(store)

		store.load([fixture.ada, fixture.bo], "profile")

		profile = fixture.ada.profile
		assert profile is not None
		assert_eq(profile.bio, "Writer")
		assert_that(fixture.bo.profile is None)


def test_loads_nested_paths_and_runs_shared_prefixes_once():
	with open_store() as store:
		fixture = Fixture(store)
		post = store.find_one(Post, fixture.ideas.id)

		with recording(store) as statements:
			store.load(post, "taggings.tag", "taggings.post")

		assert_eq(selects(statements, "taggings"), 1)
		assert_eq(
			sorted(tagging.tag.name for tagging in post.taggings),
			["Python", "Python", "Rust"],
		)
		assert_eq(
			{tagging.post.id for tagging in post.taggings},
			{post.id},
		)


def test_reloads_loaded_relationships():
	with open_store() as store:
		fixture = Fixture(store)
		post = store.find_one(Post, fixture.ideas.id)
		store.load(post, "taggings")
		fixture.tag(store, fixture.rust, 3)
		store.delete(fixture.first)

		store.load(post, "taggings.tag")

		assert_eq(by_position(post.taggings), [1, 2, 3])
		assert_eq(
			sorted(tagging.tag.name for tagging in post.taggings),
			["Python", "Rust", "Rust"],
		)


def test_shares_one_object_per_row():
	with open_store() as store:
		fixture = Fixture(store)
		taggings = store.query(Tagging).where({"tag_id": fixture.python.id}).all()

		store.load(taggings, "tag")

		assert_eq(len(taggings), 2)
		assert_that(taggings[0].tag is taggings[1].tag)


def test_splits_large_id_sets_into_batches():
	with open_store() as store:
		fixture = Fixture(store)
		for position in range(3, 8):
			fixture.tag(store, store.create(Tag, name=f"Tag {position}"), position)
		taggings = store.find_all(Tagging)
		store.connection.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 2)

		with recording(store) as statements:
			store.load(taggings, "tag")

		assert_eq(selects(statements, "tags"), 4)
		assert_eq(
			{tagging.tag.id for tagging in taggings},
			{tagging.tag_id for tagging in taggings},
		)


def test_runs_no_query_without_ids():
	with open_store() as store:
		drafts = [store.create(Draft), store.create(Draft)]

		with recording(store) as statements:
			store.load(drafts, "reviewer")

		assert_eq(statements, [])
		assert_that(all(draft.reviewer is None for draft in drafts))


def test_update_unloads_a_changed_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)
		store.load([fixture.first, fixture.second], "tag")

		store.update(fixture.first, tag_id=fixture.rust.id)
		store.update(fixture.second, tag_id=fixture.rust.id, position=4)

		with assert_raises(ModelError):
			_ = fixture.first.tag
		assert_eq(fixture.second.tag.name, "Rust")


def test_loaded_lists_are_snapshots():
	with open_store() as store:
		fixture = Fixture(store)
		store.load([fixture.ideas, fixture.empty], "taggings")

		fixture.tag(store, fixture.rust, 3)
		store.delete(fixture.second)
		store.update(fixture.third, post_id=fixture.empty.id)

		assert_eq(by_position(fixture.ideas.taggings), [0, 1, 2])
		assert_eq(fixture.empty.taggings, [])


def test_rejects_invalid_arguments_before_any_query():
	with open_store() as store:
		fixture = Fixture(store)
		constructed = Tagging(
			tag_id=fixture.python.id,
			post_id=fixture.ideas.id,
			position=9,
		)
		cases = [
			(
				lambda: store.load(fixture.first, "tag.nam"),
				(
					"store.load on Tagging has 'tag.nam', "
					"where Tag.nam is not a relationship"
				),
			),
			(
				lambda: store.load(fixture.first, "tag."),
				"store.load on Tagging has 'tag.', which is not a relationship path",
			),
			(
				lambda: store.load([fixture.first, fixture.python], "tag"),
				"store.load takes models of one model type",
			),
			(
				lambda: store.load([fixture.first, constructed], "tag"),
				"store.load can only be called with stored models",
			),
		]

		with recording(store) as statements:
			for load, message in cases:
				with assert_raises(ModelError) as raised:
					load()
				assert_eq(str(raised.exception), message)
			store.load([], "tag")

		assert_eq(statements, [])


def test_rejects_several_has_one_rows():
	with open_store() as store:
		fixture = Fixture(store)
		store.create(Profile, author_id=fixture.ada.id, bio="Reader")

		with assert_raises(DatabaseError) as raised:
			store.load(fixture.ada, "profile")

		assert_eq(
			str(raised.exception),
			f"Author.profile has several Profile rows for Author {fixture.ada.id}",
		)


def test_rejects_a_dangling_belongs_to():
	author_id, post_id, tagging_id, tag_id = uuid4(), uuid4(), uuid4(), uuid4()
	created = "2025-01-02T03:04:05.000000Z"
	rows = f"""
	INSERT INTO authors VALUES ('{author_id}', '{created}', 'Ada');
	INSERT INTO posts VALUES ('{post_id}', '{created}', 'Ideas', '{author_id}');
	INSERT INTO taggings
	VALUES ('{tagging_id}', '{created}', '{post_id}', '{tag_id}', 0);
	"""
	with open_store(rows=rows) as store:
		tagging = store.find_one(Tagging, tagging_id)

		with assert_raises(DatabaseError) as raised:
			store.load(tagging, "tag")

		assert_eq(
			str(raised.exception),
			f"Tagging.tag has no Tag row for Tagging {tagging_id}",
		)


def test_rejects_an_unregistered_target():
	with open_store([Author, Post, Tagging]) as store:
		author = store.create(Author, name="Ada")
		post = store.create(Post, title="Ideas", author_id=author.id)

		with assert_raises(ModelError):
			store.load(post, "taggings.tag")
