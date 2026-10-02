from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import (
	Config,
	Model,
	ModelError,
	Provider,
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


@contextmanager
def importable_package(name: str, files: dict[str, str]) -> Iterator[None]:
	with TemporaryDirectory() as directory:
		package = Path(directory, name)
		package.mkdir()
		Path(package, "__init__.py").touch()
		for file_name, source in files.items():
			Path(package, file_name).write_text(dedent(source))
		sys.path.insert(0, directory)
		try:
			yield
		finally:
			sys.path.remove(directory)
			for module in [*sys.modules]:
				if module == name or module.startswith(f"{name}."):
					del sys.modules[module]


def test_relationships_are_not_constructor_parameters():
	author = Author(name="Ada")
	post = Post(title="Ideas", author_id=author.id)

	with assert_raises(TypeError):
		Post(
			title="Ideas",
			author_id=author.id,
			author=author,  # ty: ignore[unknown-argument]
		)
	with assert_raises(TypeError):
		Post(
			title="Ideas",
			author_id=author.id,
			taggings=[],  # ty: ignore[unknown-argument]
		)
	with assert_raises(TypeError):
		Author(name="Ada", profile=None)  # ty: ignore[unknown-argument]
	assert_eq(post.author_id, author.id)
	assert_eq(author.name, "Ada")


def test_rejects_a_belongs_to_naming_a_missing_or_non_uuid_column():
	with assert_raises(ModelError) as missing:

		class MissingId(Model):
			tag_id: UUID
			tag: Tag = belongs_to("tag_ide")

	with assert_raises(ModelError) as not_uuid:

		class TextId(Model):
			name: str
			tag: Tag = belongs_to("name")

	assert_eq(
		str(missing.exception),
		"MissingId.tag: belongs_to names 'tag_ide', which is not a column",
	)
	assert_eq(
		str(not_uuid.exception),
		"TextId.tag: belongs_to names 'name', which does not hold a UUID",
	)


def test_rejects_wrong_annotations():
	with assert_raises(ModelError) as belongs:

		class NotAModel(Model):
			tag_id: UUID
			tag: str = belongs_to("tag_id")

	with assert_raises(ModelError) as many:

		class NotAList(Model):
			taggings: Tagging = has_many("post_id")

	with assert_raises(ModelError) as one:

		class NotOneModel(Model):
			profile: list[str] = has_one("author_id")

	with assert_raises(ModelError) as not_nullable:

		class NotNullable(Model):
			profile: Profile = has_one("author_id")

	assert_eq(
		str(belongs.exception),
		"NotAModel.tag: expected a model, got <class 'str'>",
	)
	assert_eq(
		str(many.exception),
		f"NotAList.taggings: expected list[<model>], got {Tagging!r}",
	)
	assert_eq(
		str(one.exception),
		"NotOneModel.profile: expected <model> | None, got list[str]",
	)
	assert_eq(
		str(not_nullable.exception),
		f"NotNullable.profile: expected <model> | None, got {Profile!r}",
	)


def test_checks_forward_referenced_annotations_on_first_use():
	class Note(Model):
		writer_id: UUID
		writer: list[Writer] = belongs_to("writer_id")

	class Writer(Model):
		name: str

	with assert_raises(ModelError):
		Note.relationships["writer"]


def test_resolves_targets_imported_only_for_type_checking():
	files = {
		"memoirist.py": """
			from typing import TYPE_CHECKING

			from helios.database import Model, has_many

			if TYPE_CHECKING:
				from .memoir import Memoir

			class Memoirist(Model):
				table = "memoirists"

				memoirs: list[Memoir] = has_many("memoirist_id")
		""",
		"memoir.py": """
			from typing import TYPE_CHECKING
			from uuid import UUID

			from helios.database import Model, belongs_to

			if TYPE_CHECKING:
				from .memoirist import Memoirist

			class Memoir(Model):
				table = "memoirs"

				memoirist_id: UUID
				memoirist: Memoirist = belongs_to("memoirist_id")
		""",
	}

	with importable_package("memoirs", files):
		memoirist = import_module("memoirs.memoirist").Memoirist
		memoir = import_module("memoirs.memoir").Memoir

		with assert_raises(ModelError) as unregistered:
			memoir.relationships["memoirist"]
		Provider(Config(Path("app.sqlite")), [memoirist, memoir])
		memoirs = memoirist.relationships["memoirs"].target
		author = memoir.relationships["memoirist"].target

	assert_eq(
		str(unregistered.exception),
		"Memoir.memoirist: unresolved annotation: Memoirist",
	)
	assert_that(memoirs is memoir)
	assert_that(author is memoirist)


def test_resolves_targets_declared_after_the_model():
	assert_that(Post.relationships["taggings"].target is Tagging)
	assert_that(Post.relationships["comments"].target is Comment)
	assert_that(Author.relationships["profile"].target is Profile)


def test_checks_each_relationship_when_it_is_read():
	class Note(Model):
		author_id: UUID
		author: Author | None = belongs_to("author_id")
		post_id: UUID
		post: Post = belongs_to("post_id")

	assert_that("author" in Note.relationships)
	assert_that(Note.relationships["post"].target is Post)
	with assert_raises(ModelError):
		Note.relationships["author"]


def test_rejects_a_nullability_mismatch_on_first_use():
	class Loose(Model):
		author_id: UUID
		author: Author | None = belongs_to("author_id")

	class Strict(Model):
		author_id: UUID | None = None
		author: Author = belongs_to("author_id")

	with assert_raises(ModelError) as loose:
		Loose.relationships["author"]
	with assert_raises(ModelError) as strict:
		Strict.relationships["author"]

	assert_eq(
		str(loose.exception),
		"Loose.author: annotation must include None exactly when "
		"Loose.author_id is nullable",
	)
	assert_eq(
		str(strict.exception),
		"Strict.author: annotation must include None exactly when "
		"Strict.author_id is nullable",
	)
	assert_that(Draft.relationships["reviewer"].target is Author)


def test_rejects_a_target_column_that_is_missing_or_not_a_uuid():
	class Mistargeted(Model):
		taggings: list[Tagging] = has_many("post_ide")
		positioned: list[Tagging] = has_many("position")
		profile: Profile | None = has_one("bio")

	cases = [
		("taggings", "Mistargeted.taggings: Tagging.post_ide does not hold a UUID"),
		("positioned", "Mistargeted.positioned: Tagging.position does not hold a UUID"),
		("profile", "Mistargeted.profile: Profile.bio does not hold a UUID"),
	]
	for name, message in cases:
		with assert_raises(ModelError) as raised:
			Mistargeted.relationships[name]
		assert_eq(str(raised.exception), message)


def test_reading_an_unloaded_relationship_raises():
	with open_store() as store:
		author = store.create(Author, name="Ada")
		post = store.create(Post, title="Ideas", author_id=author.id)
		stored = store.find_one(Post, post.id)
		constructed = Post(title="Ideas", author_id=author.id)

		with assert_raises(ModelError) as from_store:
			_ = stored.taggings
		with assert_raises(ModelError) as from_constructor:
			_ = constructed.author

		assert_eq(str(from_store.exception), "Post.taggings is not loaded")
		assert_eq(str(from_constructor.exception), "Post.author is not loaded")


def test_assigning_a_relationship_raises():
	tagging = Tagging(tag_id=uuid4(), post_id=uuid4(), position=0)
	post = Post(title="Ideas", author_id=uuid4())

	with assert_raises(AttributeError) as belongs:
		tagging.tag = Tag(name="Python")
	with assert_raises(AttributeError) as many:
		post.taggings = []

	assert_eq(str(belongs.exception), "Tagging.tag is read-only")
	assert_eq(str(many.exception), "Post.taggings is read-only")


def test_relationships_are_not_columns():
	with open_store() as store:
		author = store.create(Author, name="Ada")
		post = store.create(Post, title="Ideas", author_id=author.id)

		with assert_raises(ModelError) as raised:
			Post.column("author")
		with assert_raises(ModelError):
			store.query(Post).order_by("author")
		with assert_raises(ModelError):
			store.query(Post).count_by("taggings")
		with assert_raises(ModelError):
			store.update(post, author=author)
		with assert_raises(ModelError):
			store.find_by(Post, author=author)

		assert_eq(
			str(raised.exception),
			"Post.author is a relationship, not a column",
		)


def test_rejects_relationships_with_reserved_names():
	with assert_raises(ModelError):

		class Shadow(Model):
			id: Author = belongs_to("author_id")
			author_id: UUID

	with assert_raises(ModelError):

		class Meta(Model):
			relationships: list[Tagging] = has_many(  # ty: ignore[invalid-attribute-override]
				"post_id"
			)
