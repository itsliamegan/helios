from typing import Any
from uuid import UUID

from luna.test.assertion import assert_eq, assert_is, assert_is_instance, assert_raises

from helios.database import Codec, JSON, Model, ModelError, Registry, Scalar, belongs_to
from helios.database.codec import JSONText, Str


class Slug:
	def __init__(self, text: str):
		self.text = text


class SlugCodec(Codec[Slug]):
	converts = Slug

	def encode(self, value: Slug) -> Scalar:
		return value.text

	def decode(self, value: Scalar) -> Slug:
		return Slug(str(value))


class UppercaseSlugCodec(Codec[Slug]):
	converts = Slug

	def encode(self, value: Slug) -> Scalar:
		return value.text.upper()

	def decode(self, value: Scalar) -> Slug:
		return Slug(str(value).lower())


def test_root_starts_with_the_core_codecs():
	registry = Registry()

	assert_is_instance(registry.root.codec_for(str), Str)
	assert_is_instance(registry.root.codec_for(JSON[dict[str, Any]]), JSONText)


def test_finds_no_codec_for_an_unregistered_type():
	registry = Registry()

	assert_eq(registry.root.codec_for(list[str]), None)
	assert_eq(registry.root.codec_for(object), None)


def test_finds_no_codec_for_a_subclass_of_a_converted_type():
	class Title(str):
		pass

	registry = Registry()

	assert_eq(registry.root.codec_for(Title), None)


def test_encodes_a_namespaced_model_with_a_codec_in_its_namespace():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	blog = registry.namespace("blog")
	blog.model(Post)
	blog.codec(SlugCodec())

	assert_eq(Post.column("slug").encode(Slug("intro"), Post), "intro")


def test_encodes_a_namespaced_model_with_a_root_codec():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.codec(SlugCodec())
	blog = registry.namespace("blog")
	blog.model(Post)

	assert_eq(Post.column("slug").encode(Slug("intro"), Post), "intro")


def test_root_model_does_not_use_a_codec_in_a_namespace():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.model(Post)
	blog = registry.namespace("blog")
	blog.codec(SlugCodec())

	with assert_raises(ModelError):
		Post.column("slug").encode(Slug("intro"), Post)


def test_namespace_codec_wins_over_a_root_codec_for_its_models():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.codec(SlugCodec())
	blog = registry.namespace("blog")
	blog.model(Post)
	blog.codec(UppercaseSlugCodec())

	assert_eq(Post.column("slug").encode(Slug("intro"), Post), "INTRO")


def test_rebinding_a_model_in_a_new_registry_replaces_its_codecs():
	class Post(Model):
		table = "posts"
		slug: Slug

	first = Registry()
	blog = first.namespace("blog")
	blog.model(Post)
	blog.codec(UppercaseSlugCodec())
	Post.column("slug").encode(Slug("intro"), Post)
	second = Registry()
	second.model(Post)
	second.codec(SlugCodec())

	assert_eq(Post.column("slug").encode(Slug("intro"), Post), "intro")


def test_unregistered_model_has_no_codecs():
	class Post(Model):
		table = "posts"
		title: str

	with assert_raises(ModelError):
		_ = Post.column("title").codec


def test_registers_models_that_share_a_name_in_different_namespaces():
	application_post = type("Post", (Model,), {"__module__": "app", "table": "posts"})
	blog_post = type("Post", (Model,), {"__module__": "blog", "table": "blog_posts"})

	registry = Registry()
	registry.model(application_post)
	blog = registry.namespace("blog")
	blog.model(blog_post)

	assert_is(registry.get(application_post), application_post)
	assert_is(registry.get(blog_post), blog_post)


def test_resolves_a_forward_reference_within_its_namespace():
	class Post(Model):
		table = "posts"
		author_id: UUID
		author: Author = belongs_to("author_id")  # noqa: F821  # ty: ignore[unresolved-reference]

	author = type("Author", (Model,), {"table": "authors"})
	registry = Registry()
	blog = registry.namespace("blog")
	blog.model(author)
	blog.model(Post)

	assert_is(Post.relationships["author"].target, author)


def test_resolves_a_forward_reference_from_a_namespace_in_the_root():
	class Post(Model):
		table = "posts"
		author_id: UUID
		author: Author = belongs_to("author_id")  # noqa: F821  # ty: ignore[unresolved-reference]

	author = type("Author", (Model,), {"table": "authors"})
	registry = Registry()
	registry.model(author)
	blog = registry.namespace("blog")
	blog.model(Post)

	assert_is(Post.relationships["author"].target, author)


def test_root_forward_reference_does_not_find_a_namespaced_model():
	class Post(Model):
		table = "posts"
		author_id: UUID
		author: Author = belongs_to("author_id")  # noqa: F821  # ty: ignore[unresolved-reference]

	author = type("Author", (Model,), {"table": "authors"})
	registry = Registry()
	registry.model(Post)
	blog = registry.namespace("blog")
	blog.model(author)

	with assert_raises(ModelError):
		Post.relationships["author"]


def test_rejects_codecs_that_share_a_type_in_one_namespace():
	registry = Registry()
	registry.codec(SlugCodec())

	with assert_raises(ModelError):
		registry.codec(UppercaseSlugCodec())


def test_rejects_models_that_share_a_name_in_one_namespace():
	first = type("Post", (Model,), {"__module__": "first", "table": "posts"})
	second = type("Post", (Model,), {"__module__": "second", "table": "posts"})
	registry = Registry()
	registry.model(first)

	with assert_raises(ModelError):
		registry.model(second)


def test_rejects_a_namespace_name_used_twice():
	registry = Registry()
	registry.namespace("blog")

	with assert_raises(ModelError):
		registry.namespace("blog")


def test_rejects_a_model_registered_twice():
	class Post(Model):
		table = "posts"

	registry = Registry()
	registry.model(Post)
	blog = registry.namespace("blog")

	with assert_raises(ModelError):
		blog.model(Post)


def test_rejects_a_model_without_a_table():
	class Post(Model):
		pass

	registry = Registry()

	with assert_raises(ModelError):
		registry.model(Post)


def test_rejects_a_class_that_is_not_a_model():
	registry = Registry()

	with assert_raises(ModelError):
		registry.model(object)  # ty: ignore[invalid-argument-type]


def test_rejects_an_unregistered_model():
	class Post(Model):
		table = "posts"

	registry = Registry()

	with assert_raises(ModelError):
		registry.get(Post)
