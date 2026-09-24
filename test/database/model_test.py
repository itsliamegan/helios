from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Model, ModelError, attribute


def test_constructs_model_with_table_defaults_and_nulls():
	class Post(Model):
		table = "posts"
		title = attribute(str)
		published = attribute(bool, default=False)
		summary = attribute(str, nullable=True)

	post = Post(title="Intro")

	assert_eq(Post.table, "posts")
	assert_eq(post.title, "Intro")
	assert_eq(post.published, False)
	assert_eq(post.summary, None)
	assert_that(isinstance(post.id, UUID))
	assert_that(post.created_at is None)


def test_preserves_explicit_null_instead_of_default():
	class Post(Model):
		title = attribute(str, default="Untitled", nullable=True)

	assert_that(Post(title=None).title is None)


def test_assigns_canonical_values_and_nulls():
	class Post(Model):
		title = attribute(str)
		summary = attribute(str, nullable=True)

	post = Post(title="Intro")
	post.title = "Revised"
	post.summary = "Short"
	post.summary = None

	assert_eq(post.title, "Revised")
	assert_that(post.summary is None)


def test_failed_assignment_preserves_value():
	class Post(Model):
		points = attribute(int)

	post = Post(points=3)
	with assert_raises(ModelError):
		post.points = True

	assert_eq(post.points, 3)


def test_rejects_missing_extra_non_init_and_null_attributes():
	class Post(Model):
		title = attribute(str)

	with assert_raises(ModelError):
		Post()
	with assert_raises(ModelError):
		Post(title="Intro", extra="value")
	with assert_raises(ModelError):
		Post(title="Intro", id=uuid4())
	with assert_raises(ModelError):
		Post(title=None)


def test_inherits_and_overrides_attributes():
	class Content(Model):
		title = attribute(str)
		score = attribute(str)

	class Post(Content):
		table = "posts"
		score = attribute(int)

	post = Post(title="Intro", score=3)

	assert_eq(post.title, "Intro")
	assert_eq(post.score, 3)


def test_rejects_reserved_and_invalid_inherited_overrides():
	with assert_raises(ModelError):

		class Reserved(Model):
			id = attribute(UUID)

	class Content(Model):
		title = attribute(str)

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
