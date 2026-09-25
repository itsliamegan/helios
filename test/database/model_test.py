from typing import ClassVar
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Model, ModelError, attribute


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
	assert_that(post.created_at is None)


def test_preserves_explicit_null_instead_of_default():
	class Post(Model):
		title: str | None = "Untitled"

	assert_that(Post(title=None).title is None)


def test_assigns_canonical_values_and_nulls():
	class Post(Model):
		title: str
		summary: str | None = None

	post = Post(title="Intro")
	post.title = "Revised"
	post.summary = "Short"
	post.summary = None

	assert_eq(post.title, "Revised")
	assert_that(post.summary is None)


def test_failed_assignment_preserves_value():
	class Post(Model):
		points: int

	post = Post(points=3)
	with assert_raises(ModelError):
		post.points = True

	assert_eq(post.points, 3)


def test_rejects_missing_extra_non_init_and_null_attributes():
	class Post(Model):
		title: str

	with assert_raises(TypeError) as missing:
		Post()
	with assert_raises(TypeError) as extra:
		Post(title="Intro", extra="value")
	with assert_raises(TypeError) as reserved:
		Post(title="Intro", id=uuid4())
	with assert_raises(ModelError):
		Post(title=None)

	assert_eq(str(missing.exception), "Post is missing attributes: title")
	assert_eq(str(extra.exception), "Post got unexpected attributes: extra")
	assert_eq(str(reserved.exception), "Post got unexpected attributes: id")


def test_requires_nullable_attributes_without_defaults():
	class Post(Model):
		summary: str | None

	with assert_raises(TypeError):
		Post()
	assert_that(Post(summary=None).summary is None)


def test_declares_attributes_only_from_instance_annotations():
	class Post(Model):
		table = "posts"
		kind: ClassVar[str] = "post"
		title: str

	assert_eq(list(Post.attributes), ["id", "created_at", "title"])


def test_resolves_codecs_nested_in_the_model():
	class Post(Model):
		class Slug:
			def __init__(self, text: str):
				self.text = text

			@classmethod
			def check(cls, value: object):
				if not isinstance(value, cls):
					raise TypeError("expected a Slug")

			@classmethod
			def encode(cls, value: Post.Slug) -> str:
				return value.text

			@classmethod
			def decode(cls, value: object) -> Post.Slug:
				return cls(str(value))

		slug: Slug

	post = Post(slug=Post.Slug("intro"))

	assert_eq(post.slug.text, "intro")
	with assert_raises(ModelError):
		Post(slug="intro")


def test_resolves_codecs_that_refer_to_the_model():
	class Post(Model):
		class Slug:
			def __init__(self, text: str):
				self.text = text

			@classmethod
			def check(cls, value: object):
				if not isinstance(value, cls):
					raise TypeError("expected a Slug")

			@classmethod
			def encode(cls, value: Post.Slug) -> str:
				return value.text

			@classmethod
			def decode(cls, value: object) -> Post.Slug:
				return cls(str(value))

		slug: Post.Slug | None = None

	post = Post(slug=Post.Slug("intro"))

	assert_eq(post.slug.text, "intro")
	with assert_raises(ModelError):
		Post(slug="intro")


def test_resolves_codecs_declared_after_the_model():
	class Post(Model):
		slug: Slug

	class Slug:
		def __init__(self, text: str):
			self.text = text

		@classmethod
		def check(cls, value: object):
			if not isinstance(value, cls):
				raise TypeError("expected a Slug")

		@classmethod
		def encode(cls, value: Slug) -> str:
			return value.text

		@classmethod
		def decode(cls, value: object) -> Slug:
			return cls(str(value))

	post = Post(slug=Slug("intro"))

	assert_eq(post.slug.text, "intro")


def test_rejects_unresolved_annotations_on_construction():
	class Post(Model):
		author: Author  # noqa: F821

	with assert_raises(ModelError) as raised:
		Post(author=None)

	assert_eq(str(raised.exception), "Post.author: unresolved annotation: Author")


def test_rejects_attributes_without_supported_annotations():
	with assert_raises(ModelError):

		class Unannotated(Model):
			title = attribute(default="")

	with assert_raises(ModelError):

		class Unsupported(Model):
			score: float

	with assert_raises(ModelError):

		class Ambiguous(Model):
			value: str | int | None

	with assert_raises(ModelError):

		class Alternative(Model):
			value: str | int


def test_declaration_errors_are_type_errors():
	with assert_raises(TypeError) as raised:

		class Unsupported(Model):
			score: float

	assert_that(isinstance(raised.exception, ModelError))


def test_inherits_and_overrides_attributes():
	class Content(Model):
		title: str
		score: str

	class Post(Content):
		table = "posts"
		score: int

	post = Post(title="Intro", score=3)

	assert_eq(post.title, "Intro")
	assert_eq(post.score, 3)


def test_rejects_reserved_and_invalid_inherited_overrides():
	with assert_raises(ModelError):

		class Reserved(Model):
			id: UUID

	class Content(Model):
		title: str

	with assert_raises(ModelError):

		class Post(Content):
			title = "Intro"


def test_rejects_multiple_model_bases():
	class Content(Model):
		pass

	class Publishable(Model):
		pass

	with assert_raises(ModelError):

		class Post(Content, Publishable):
			pass
