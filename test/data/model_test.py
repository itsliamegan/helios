from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.data.model import Model, ModelError, attr


def test_stores_metadata():
	class Post(Model):
		pass

	assert_that(Post.id is not None)
	assert_that(Post.created_at is not None)


def test_init_attrs():
	class Post(Model):
		title = attr(str)

	post = Post(title="Intro")

	assert_that(post.id is not None)
	assert_that(post.created_at is None)
	assert_eq(post.title, "Intro")


def test_defaults_attr():
	class Post(Model):
		unread = attr(bool, default=True)

	post = Post()

	assert_eq(post.unread, True)


def test_preserves_null_with_default():
	class Post(Model):
		title = attr(str, default="Untitled", nullable=True)

	post = Post(title=None)

	assert_eq(post.title, None)


def test_missing_nullable_attr_is_null():
	class Post(Model):
		title = attr(str, nullable=True)

	post = Post()

	assert_eq(post.title, None)


def test_rejects_wrong_attr_type():
	class Post(Model):
		points = attr(int)

	with assert_raises(ModelError) as raised:
		Post(points=True)

	assert_eq(str(raised.exception), "Post.points: expected an integer, got bool")


def test_rejects_wrong_default_type():
	class Post(Model):
		points = attr(int, default=True)

	with assert_raises(ModelError) as raised:
		Post()

	assert_eq(str(raised.exception), "Post.points: expected an integer, got bool")


def test_preserves_false_with_default():
	class Post(Model):
		unread = attr(bool, default=True)

	post = Post(unread=False)

	assert_eq(post.unread, False)


def test_rejects_non_init_attr():
	class Post(Model):
		pass

	with assert_raises(ModelError):
		Post(id=uuid4())


def test_requires_attr():
	class Post(Model):
		title = attr(str)

	with assert_raises(ModelError):
		Post()


def test_rejects_extra_attr():
	class Post(Model):
		pass

	with assert_raises(ModelError):
		Post(title="Intro")


def test_rejects_null_attr():
	class Post(Model):
		title = attr(str)

	with assert_raises(ModelError):
		Post(title=None)


def test_rejects_builtin_override():
	with assert_raises(ModelError):

		class Post(Model):
			id = attr(UUID)


def test_infers_attr_name():
	class Post(Model):
		title = attr(str)

	assert_eq(Post.title.name, "title")
	assert_that(Post.attrs["title"] is Post.title)


def test_assigns_attr():
	class Post(Model):
		title = attr(str)

	post = Post(title="Intro")
	post.title = "Revised"

	assert_eq(post.title, "Revised")


def test_assigns_null_attr():
	class Post(Model):
		title = attr(str, nullable=True)

	post = Post(title="Intro")
	post.title = None

	assert_eq(post.title, None)


def test_failed_assignment_preserves_state():
	class Post(Model):
		points = attr(int)

	post = Post(points=3)

	with assert_raises(ModelError) as raised:
		post.points = True

	assert_eq(str(raised.exception), "Post.points: expected an integer, got bool")
	assert_eq(post.points, 3)
	assert_eq(post._old_values, {})


def test_rejects_null_assignment():
	class Post(Model):
		title = attr(str)

	post = Post(title="Intro")

	with assert_raises(ModelError) as raised:
		post.title = None

	assert_eq(str(raised.exception), "Post.title: cannot be null")
	assert_eq(post.title, "Intro")


def test_inherits_attrs():
	class Content(Model):
		title = attr(str)

	class Post(Content):
		body = attr(str)

	post = Post(title="Intro", body="Welcome")

	assert_that(Post.title is not None)
	assert_that(Post.body is not None)
	assert_eq(post.title, "Intro")
	assert_eq(post.body, "Welcome")


def test_rejects_multiple_bases():
	class Content(Model):
		pass

	class Publishable(Model):
		pass

	with assert_raises(ModelError):

		class Post(Content, Publishable):
			pass


def test_overrides_attr():
	class Content(Model):
		score = attr(str)

	class Post(Content):
		score = attr(int)

	post = Post(score=3)

	assert_eq(post.score, 3)


def test_rejects_non_attr_override():
	class Content(Model):
		title = attr(str)

	with assert_raises(ModelError):

		class Post(Content):
			title = "Intro"
