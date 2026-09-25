from typing import ClassVar

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.declaration import (
	Declaration,
	DeclarationError,
	MISSING,
	check_init_keywords,
	check_single_base,
	declarations,
	split_nullable,
)


class ExampleError(TypeError):
	pass


def annotation_of(declaration: Declaration[object]) -> object:
	return declaration.annotation


def reject(declaration: Declaration[object]) -> object:
	raise DeclarationError(declaration.name, "not allowed")


def test_reads_annotations_with_defaults():
	class Pin:
		limit: ClassVar[int] = 10

		title: str
		note: str = ""

	found = declarations(Pin, annotation_of, ExampleError)

	assert_eq([declaration.name for declaration in found], ["title", "note"])
	assert_that(found[0].default is MISSING)
	assert_eq(found[1].default, "")
	assert_eq([declaration.resolve() for declaration in found], [str, str])


def test_settles_resolved_annotations_when_declared():
	class Pin:
		title: str

	with assert_raises(ExampleError) as raised:
		declarations(Pin, reject, ExampleError)

	assert_eq(str(raised.exception), "Pin.title: not allowed")


def test_rejects_string_annotations():
	class Pin:
		title: "str"  # noqa: UP037

	with assert_raises(ExampleError) as raised:
		declarations(Pin, annotation_of, ExampleError)

	assert_eq(
		str(raised.exception),
		"Pin.title: string annotations are not supported: 'str'",
	)


def test_resolves_pending_annotations_on_first_use():
	class Pin:
		board: Board

	(declaration,) = declarations(Pin, annotation_of, ExampleError)
	pending = declaration.pending

	class Board:
		pass

	resolved = declaration.resolve()

	assert_that(pending)
	assert_that(not declaration.pending)
	assert_that(resolved is Board)


def test_rejects_annotations_that_never_resolve():
	class Pin:
		board: Board  # noqa: F821

	(declaration,) = declarations(Pin, annotation_of, ExampleError)

	with assert_raises(ExampleError) as raised:
		declaration.resolve()

	assert_eq(str(raised.exception), "Pin.board: unresolved annotation: Board")


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
