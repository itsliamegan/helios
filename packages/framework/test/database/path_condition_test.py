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
		self.ada = store.create(Author, name="Ada")
		self.bo = store.create(Author, name="Bo")
		self.cy = store.create(Author, name="Cy")
		store.create(Profile, author_id=self.ada.id, bio="Writer")
		self.ideas = store.create(Post, title="Ideas", author_id=self.ada.id)
		self.plans = store.create(Post, title="Plans", author_id=self.bo.id)
		self.secret = store.create(Post, title="Secret", author_id=self.cy.id)
		store.create(Comment, post_id=self.plans.id, author_id=self.ada.id)
		self.python = store.create(Tag, name="Python")
		self.rust = store.create(Tag, name="Rust")
		self.sql = store.create(Tag, name="SQL")
		self.python_on_ideas = self.tag(store, self.python, self.ideas, 0)
		self.rust_on_ideas = self.tag(store, self.rust, self.ideas, 1)
		self.python_on_plans = self.tag(store, self.python, self.plans, 1)
		self.sql_on_plans = self.tag(store, self.sql, self.plans, 0)
		self.python_on_secret = self.tag(store, self.python, self.secret, 0)
		self.rust_on_secret = self.tag(store, self.rust, self.secret, 1)

	def tag(self, store: Store, tag: Tag, post: Post, position: int) -> Tagging:
		return store.create(
			Tagging,
			tag_id=tag.id,
			post_id=post.id,
			position=position,
		)


def titles(posts: list[Post]) -> set[str]:
	return {post.title for post in posts}


def names(models: list[Author] | list[Tag]) -> set[str]:
	return {model.name for model in models}


def ids(models: list[Tagging] | list[Draft]) -> set[UUID]:
	return {model.id for model in models}


def test_filters_through_belongs_to():
	with open_store() as store:
		fixture = Fixture(store)

		found = store.query(Tagging).where({"post.title": "Plans"}).all()

		assert_eq(
			ids(found),
			{fixture.python_on_plans.id, fixture.sql_on_plans.id},
		)


def test_filters_through_has_many_and_has_one():
	with open_store() as store:
		fixture = Fixture(store)

		posts = store.query(Post).where({"taggings.tag_id": fixture.sql.id})
		authors = store.query(Author).where({"profile.bio": "Writer"})

		assert_eq(titles(posts.all()), {"Plans"})
		assert_eq(names(authors.all()), {"Ada"})


def test_filters_through_nested_paths():
	with open_store() as store:
		Fixture(store)

		found = store.query(Tag).where({"taggings.post.title": "Secret"}).all()

		assert_eq(names(found), {"Python", "Rust"})


def test_applies_access_rules():
	with open_store() as store:
		fixture = Fixture(store)
		author = fixture.ada.id

		posts = store.query(Post).where_any(
			{"author_id": author},
			{"comments.author_id": author},
		)
		taggings = (
			store.query(Tagging)
			.where({"tag_id": fixture.python.id})
			.where_any({"post.author_id": author}, {"post.comments.author_id": author})
		)

		assert_eq(titles(posts.all()), {"Ideas", "Plans"})
		assert_eq(
			ids(taggings.all()),
			{fixture.python_on_ideas.id, fixture.python_on_plans.id},
		)


def test_keys_under_one_path_apply_to_the_same_related_row():
	with open_store() as store:
		fixture = Fixture(store)
		conditions = {"taggings.position": 0, "taggings.tag_id": fixture.rust.id}

		together = store.query(Post).where(conditions).all()
		apart = (
			store.query(Post)
			.where({"taggings.position": 0})
			.where({"taggings.tag_id": fixture.rust.id})
			.all()
		)
		grouped = (
			store.query(Post)
			.where_any({"taggings.position": 0})
			.where_any({"taggings.tag_id": fixture.rust.id})
			.all()
		)

		assert_eq(together, [])
		assert_eq(titles(apart), {"Ideas", "Secret"})
		assert_eq(titles(grouped), {"Ideas", "Secret"})


def test_nests_paths_under_a_shared_relationship():
	with open_store() as store:
		fixture = Fixture(store)

		found = (
			store.query(Tag)
			.where(
				{
					"taggings.position": 0,
					"taggings.post.author_id": fixture.bo.id,
				}
			)
			.all()
		)

		assert_eq(names(found), {"SQL"})


def test_where_not_is_the_exact_complement_of_a_path():
	with open_store() as store:
		fixture = Fixture(store)
		reviewed = store.create(Draft, reviewer_id=fixture.ada.id)
		other = store.create(Draft, reviewer_id=fixture.bo.id)
		unreviewed = store.create(Draft)

		kept = store.query(Draft).where({"reviewer.name": "Ada"}).all()
		dropped = store.query(Draft).where_not({"reviewer.name": "Ada"}).all()

		assert_eq(ids(kept), {reviewed.id})
		assert_eq(ids(dropped), {other.id, unreviewed.id})


def test_follows_a_path_through_the_same_table_twice():
	with open_store() as store:
		fixture = Fixture(store)

		found = (
			store.query(Tagging).where({"post.taggings.tag_id": fixture.sql.id}).all()
		)

		assert_eq(
			ids(found),
			{fixture.python_on_plans.id, fixture.sql_on_plans.id},
		)


def test_count_by_and_exists_respect_paths():
	with open_store() as store:
		fixture = Fixture(store)
		commented = store.query(Tagging).where(
			{"post.comments.author_id": fixture.ada.id}
		)

		assert_eq(
			commented.count_by("tag_id"),
			{fixture.python.id: 1, fixture.sql.id: 1},
		)
		assert_eq(commented.exists(), True)
		assert_eq(
			store.query(Post).where({"comments.author_id": fixture.cy.id}).exists(),
			False,
		)


def test_rejects_invalid_paths():
	with open_store() as store:
		cases = [
			("tag_id.name", "where Tagging.tag_id is not a relationship"),
			("post", "where Tagging.post is not a column"),
			("post.titel", "where Post.titel is not a column"),
			("post..title", "which is not of the form 'name' or 'name operator'"),
		]
		for key, detail in cases:
			with assert_raises(ModelError) as raised:
				store.query(Tagging).where({key: "Ideas"})
			assert_eq(str(raised.exception), f"Query on Tagging has {key!r}, {detail}")


def test_checks_values_against_the_final_column():
	with open_store() as store, assert_raises(ModelError):
		store.query(Tagging).where({"post.title": 1})
