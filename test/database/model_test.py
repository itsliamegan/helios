from typing import ClassVar
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Codec, Model, ModelError, Scalar, generated


def test_constructs_model_with_table_defaults_and_nulls():
	class Post(Model):
		table = "posts"
		title: str
		published: bool = False
		summary: str | None = None

	post = Post(title="Intro")

	assert_eq(Post.table, "posts")
	assert_eq(post.title, "Intro")
	assert_eq(post.published, False)
	assert_eq(post.summary, None)
	assert_that(isinstance(post.id, UUID))


def test_constructed_model_has_no_created_at():
	class Post(Model):
		title: str

	post = Post(title="Intro")

	with assert_raises(AttributeError):
		_ = post.created_at


def test_preserves_explicit_null_instead_of_default():
	class Post(Model):
		title: str | None = "Untitled"

	assert_that(Post(title=None).title is None)


def test_assigning_a_column_raises_and_keeps_the_value():
	class Post(Model):
		title: str

	post = Post(title="Intro")
	original_id = post.id

	with assert_raises(AttributeError) as raised:
		post.title = "Revised"
	with assert_raises(AttributeError):
		post.id = uuid4()

	exception = raised.exception
	assert exception is not None
	assert_that("Post.title" in str(exception))
	assert_that("store.update" in str(exception))
	assert_eq(post.title, "Intro")
	assert_eq(post.id, original_id)


def test_rejects_missing_extra_non_init_and_null_columns():
	class Post(Model):
		title: str

	with assert_raises(TypeError):
		Post()  # ty: ignore[missing-argument]
	with assert_raises(TypeError):
		Post(title="Intro", extra="value")  # ty: ignore[unknown-argument]
	with assert_raises(TypeError):
		Post(title="Intro", id=uuid4())  # ty: ignore[unknown-argument]
	with assert_raises(ModelError):
		Post(title=None)  # ty: ignore[invalid-argument-type]


def test_requires_nullable_columns_without_defaults():
	class Post(Model):
		summary: str | None

	with assert_raises(TypeError):
		Post()  # ty: ignore[missing-argument]
	assert_that(Post(summary=None).summary is None)


def test_declares_columns_only_from_instance_annotations():
	class Post(Model):
		table = "posts"
		kind: ClassVar[str] = "post"
		title: str

	assert_eq(list(Post.columns), ["id", "created_at", "title"])


def test_resolves_codecs_nested_in_the_model():
	class Post(Model):
		class Slug:
			def __init__(self, text: str):
				self.text = text

			class Codec(Codec):
				def check(self, value: object):
					if not isinstance(value, Post.Slug):
						raise TypeError("expected a Slug")

				def encode(self, value: Post.Slug) -> Scalar:
					return value.text

				def decode(self, value: Scalar) -> Post.Slug:
					return Post.Slug(str(value))

		slug: Slug

	post = Post(slug=Post.Slug("intro"))

	assert_eq(post.slug.text, "intro")
	with assert_raises(ModelError):
		Post(slug="intro")  # ty: ignore[invalid-argument-type]


def test_resolves_codecs_that_refer_to_the_model():
	class Post(Model):
		class Slug:
			def __init__(self, text: str):
				self.text = text

			class Codec(Codec):
				def check(self, value: object):
					if not isinstance(value, Post.Slug):
						raise TypeError("expected a Slug")

				def encode(self, value: Post.Slug) -> Scalar:
					return value.text

				def decode(self, value: Scalar) -> Post.Slug:
					return Post.Slug(str(value))

		slug: Post.Slug | None = None

	post = Post(slug=Post.Slug("intro"))

	assert post.slug is not None
	assert_eq(post.slug.text, "intro")
	with assert_raises(ModelError):
		Post(slug="intro")  # ty: ignore[invalid-argument-type]


def test_resolves_codecs_declared_after_the_model():
	class Post(Model):
		slug: Slug

	class Slug:
		def __init__(self, text: str):
			self.text = text

		class Codec(Codec):
			def check(self, value: object):
				if not isinstance(value, Slug):
					raise TypeError("expected a Slug")

			def encode(self, value: Slug) -> Scalar:
				return value.text

			def decode(self, value: Scalar) -> Slug:
				return Slug(str(value))

	post = Post(slug=Slug("intro"))

	assert_eq(post.slug.text, "intro")


def test_rejects_unresolved_annotations_on_construction():
	class Post(Model):
		author: Author  # noqa: F821  # ty: ignore[unresolved-reference]

	with assert_raises(ModelError):
		Post(author=None)


def test_resolves_each_column_when_it_is_read():
	class Post(Model):
		title: str
		author: Author  # noqa: F821  # ty: ignore[unresolved-reference]

	assert_that("author" in Post.columns)
	assert_eq(Post.column("title").name, "title")
	with assert_raises(ModelError):
		Post.columns["author"]


def test_rejects_columns_without_supported_annotations():
	with assert_raises(ModelError):

		class Unannotated(Model):
			title = generated()

	with assert_raises(ModelError):

		class Unsupported(Model):
			score: dict[str, str]

	with assert_raises(ModelError):

		class Ambiguous(Model):
			value: str | int | None

	with assert_raises(ModelError):

		class Alternative(Model):
			value: str | int


def test_rejects_subclassing_a_model():
	class Content(Model):
		title: str

	with assert_raises(ModelError):

		class Post(Content):
			table = "posts"


def test_rejects_redeclaring_model_attributes():
	with assert_raises(ModelError):

		class Annotated(Model):
			id: UUID

	with assert_raises(ModelError):

		class Assigned(Model):
			created_at = None


def test_rejects_attributes_named_like_model_metadata():
	with assert_raises(ModelError):

		class Annotated(Model):
			columns: str  # ty: ignore[invalid-attribute-override]

	with assert_raises(ModelError):

		class Assigned(Model):
			columns = {}


def test_rejects_attributes_named_like_model_members():
	with assert_raises(ModelError):

		class Annotated(Model):
			hydrate: str

	with assert_raises(ModelError):

		class Assigned(Model):
			column = None


def test_declares_a_column_named_values():
	class Tally(Model):
		values: str

	assert_eq(Tally(values="a").values, "a")


def test_rejects_multiple_model_bases():
	class Content(Model):
		pass

	class Publishable(Model):
		pass

	with assert_raises(ModelError):

		class Post(Content, Publishable):
			pass
