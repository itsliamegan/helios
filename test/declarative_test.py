from typing import ClassVar

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.declarative import (
	DeclarationError,
	MISSING,
	check_init_keywords,
	check_single_base,
	declarations,
	split_nullable,
)


class ExampleError(TypeError):
	pass


class Lookup:
	def __init__(self, *held: type):
		self.held = {each.__name__: each for each in held}

	def find(self, name: str) -> type | None:
		return self.held.get(name)


def test_reads_annotations_with_defaults():
	class Post:
		limit: ClassVar[int] = 10

		title: str
		note: str = ""

	found = declarations(Post, ExampleError)

	assert_eq([declaration.name for declaration in found], ["title", "note"])
	assert_that(found[0].default is MISSING)
	assert_eq(found[1].default, "")
	assert_eq([declaration.resolve() for declaration in found], [str, str])


def test_rejects_with_the_owner_error():
	class Post:
		title: str

	(declaration,) = declarations(Post, ExampleError)
	rejected = declaration.reject(DeclarationError("title", "not allowed"))

	assert_that(isinstance(rejected, ExampleError))
	assert_eq(str(rejected), "Post.title: not allowed")


def test_rejects_string_annotations():
	class Post:
		title: "str"  # noqa: UP037

	with assert_raises(ExampleError) as raised:
		declarations(Post, ExampleError)

	assert_eq(
		str(raised.exception),
		"Post.title: string annotations are not supported: 'str'",
	)


def test_resolves_pending_annotations_on_first_use():
	class Post:
		author: Author

	(declaration,) = declarations(Post, ExampleError)
	pending = declaration.pending

	class Author:
		pass

	resolved = declaration.resolve()

	assert_that(pending)
	assert_that(not declaration.pending)
	assert_that(resolved is Author)


def test_rejects_annotations_that_never_resolve():
	class Post:
		author: Author  # noqa: F821  # ty: ignore[unresolved-reference]

	(declaration,) = declarations(Post, ExampleError)

	with assert_raises(ExampleError) as raised:
		declaration.resolve()

	assert_eq(str(raised.exception), "Post.author: unresolved annotation: Author")


def test_looks_up_unresolved_names_in_the_fallback():
	biographer = type("Biographer", (), {})

	class Post:
		author: Biographer | None  # noqa: F821  # ty: ignore[unresolved-reference]
		editor: Editor

	author, editor = declarations(Post, ExampleError)
	author.fallback = Lookup(biographer)

	class Editor:
		pass

	assert_eq(author.resolve(), biographer | None)
	assert_that(editor.resolve() is Editor)


def test_resolves_each_annotation_on_its_own():
	class Post:
		author: Biographer  # noqa: F821  # ty: ignore[unresolved-reference]
		editor: Editor

	author, editor = declarations(Post, ExampleError)

	class Editor:
		pass

	assert_that(editor.resolve() is Editor)
	with assert_raises(ExampleError):
		author.resolve()


def test_rejects_names_the_fallback_does_not_hold():
	class Post:
		author: Biographer  # noqa: F821  # ty: ignore[unresolved-reference]

	(declaration,) = declarations(Post, ExampleError)
	declaration.fallback = Lookup()

	with assert_raises(ExampleError) as raised:
		declaration.resolve()

	assert_eq(str(raised.exception), "Post.author: unresolved annotation: Biographer")


def test_splits_nullable_annotations():
	assert_eq(split_nullable("count", int), (int, False))
	assert_eq(split_nullable("count", int | None), (int, True))
	assert_eq(split_nullable("count", None | int), (int, True))


def test_rejects_unions_other_than_nullable():
	with assert_raises(DeclarationError) as raised:
		split_nullable("value", str | int)

	assert_eq(str(raised.exception), "value: unsupported type: str | int")


def test_rejects_unexpected_init_keywords():
	class Post:
		pass

	with assert_raises(TypeError) as raised:
		check_init_keywords(Post, "attributes", ["title", "extra"], ["title"], [])

	assert_eq(str(raised.exception), "Post got unexpected attributes: extra")


def test_rejects_missing_init_keywords():
	class Post:
		pass

	with assert_raises(TypeError) as raised:
		check_init_keywords(Post, "attributes", [], ["title", "body"], ["title"])

	assert_eq(str(raised.exception), "Post is missing attributes: title")


def test_requires_a_single_base():
	class Record:
		pass

	class Post(Record):
		pass

	class Content(Record):
		pass

	class Article(Content):
		pass

	class Timestamped:
		pass

	class Note(Record, Timestamped):
		pass

	check_single_base(Post, Record, ExampleError)
	with assert_raises(ExampleError) as subclass_raised:
		check_single_base(Article, Record, ExampleError)
	with assert_raises(ExampleError) as mixin_raised:
		check_single_base(Note, Record, ExampleError)

	assert_eq(str(subclass_raised.exception), "Article must inherit only from Record")
	assert_eq(str(mixin_raised.exception), "Note must inherit only from Record")
