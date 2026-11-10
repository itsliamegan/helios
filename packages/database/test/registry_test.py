from typing import Any
from uuid import UUID

from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_is_instance,
	assert_not_none,
	assert_raises,
)

from helios.database import JSON, Model, ModelError, Registry, belongs_to
from helios.database.codec import Codec, JSONText, Scalar, Str


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

	assert_is_instance(registry.namespaces.root.codecs.find(str), Str)
	assert_is_instance(
		registry.namespaces.root.codecs.find(JSON[dict[str, Any]]), JSONText
	)


def test_finds_no_codec_for_an_unregistered_type():
	registry = Registry()

	assert_eq(registry.namespaces.root.codecs.find(list[str]), None)
	assert_eq(registry.namespaces.root.codecs.find(object), None)


def test_finds_no_codec_for_a_subclass_of_a_converted_type():
	class Title(str):
		pass

	registry = Registry()

	assert_eq(registry.namespaces.root.codecs.find(Title), None)


def test_encodes_a_namespaced_model_with_a_codec_in_its_namespace():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	blog = registry.namespace("blog")
	blog.model(Post)
	blog.codec(SlugCodec())
	namespace = assert_not_none(registry.namespaces.find(Post))

	assert_eq(Post.column("slug").codec(namespace).encode(Slug("intro")), "intro")


def test_encodes_a_namespaced_model_with_a_root_codec():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.codec(SlugCodec())
	blog = registry.namespace("blog")
	blog.model(Post)
	namespace = assert_not_none(registry.namespaces.find(Post))

	assert_eq(Post.column("slug").codec(namespace).encode(Slug("intro")), "intro")


def test_root_model_does_not_use_a_codec_in_a_namespace():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.model(Post)
	blog = registry.namespace("blog")
	blog.codec(SlugCodec())
	namespace = assert_not_none(registry.namespaces.find(Post))

	with assert_raises(ModelError):
		Post.column("slug").codec(namespace)


def test_namespace_codec_wins_over_a_root_codec_for_its_models():
	class Post(Model):
		table = "posts"
		slug: Slug

	registry = Registry()
	registry.codec(SlugCodec())
	blog = registry.namespace("blog")
	blog.model(Post)
	blog.codec(UppercaseSlugCodec())
	namespace = assert_not_none(registry.namespaces.find(Post))

	assert_eq(Post.column("slug").codec(namespace).encode(Slug("intro")), "INTRO")


def test_keeps_the_codecs_of_each_registry_that_holds_a_model():
	class Post(Model):
		table = "posts"
		slug: Slug

	first = Registry()
	blog = first.namespace("blog")
	blog.model(Post)
	blog.codec(UppercaseSlugCodec())
	second = Registry()
	second.model(Post)
	second.codec(SlugCodec())
	first_namespace = assert_not_none(first.namespaces.find(Post))
	second_namespace = assert_not_none(second.namespaces.find(Post))

	column = Post.column("slug")
	assert_eq(column.codec(first_namespace).encode(Slug("intro")), "INTRO")
	assert_eq(column.codec(second_namespace).encode(Slug("intro")), "intro")


def test_finds_no_namespace_for_an_unregistered_model():
	class Post(Model):
		table = "posts"

	registry = Registry()

	assert_eq(registry.namespaces.find(Post), None)


def test_registers_models_that_share_a_name_in_different_namespaces():
	application_post = type("Post", (Model,), {"__module__": "app", "table": "posts"})
	blog_post = type("Post", (Model,), {"__module__": "blog", "table": "blog_posts"})

	registry = Registry()
	registry.model(application_post)
	blog = registry.namespace("blog")
	blog.model(blog_post)

	assert_is(registry.namespaces.find(application_post), registry.namespaces.root)
	assert_is(registry.namespaces.find(blog_post), blog)


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

	assert_eq(Post.relationships["author"].target_types, (author,))


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

	assert_eq(Post.relationships["author"].target_types, (author,))


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
