from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.store import (
	Model,
	ModelError,
	NotFoundError,
	Schema,
	Store,
	attr,
	decode,
	encode,
)


def test_creates_model_with_builtin_attrs():
	class Post(Model):
		pass

	store = Store()

	created = store.create(Post)

	assert_that(created.id is not None)
	assert_that(created.created_at is not None)


def test_stores_model_metadata():
	class Post(Model):
		pass

	assert_that(Post.id is not None)
	assert_that(Post.created_at is not None)


def test_constructs_unsaved_model():
	class Post(Model):
		title = attr(str)

	new = Post(title="Intro")

	assert_that(new.id is not None)
	assert_that(new.created_at is None)
	assert_eq(new.title, "Intro")


def test_adds_model_to_store():
	class Post(Model):
		pass

	new = Post()
	store = Store()

	store.add(new)
	created_at = new.created_at
	store.add(new)

	assert_that(created_at is not None)
	assert_eq(new.created_at, created_at)
	assert_that(store.find_one(Post, new.id) is new)


def test_doesnt_accept_non_init_attrs():
	class Post(Model):
		pass

	with assert_raises(ModelError):
		Store().create(Post, id=uuid4())


def test_doesnt_override_builtin_attrs():
	with assert_raises(ModelError):

		class Post(Model):
			id = attr(UUID)


def test_creates_model_with_attr():
	class Post(Model):
		title = attr(str)

	store = Store()

	created = store.create(Post, title="Intro")

	assert_eq(created.title, "Intro")


def test_infers_attr_name_from_class_assignment():
	class Post(Model):
		title = attr(str)

	assert_eq(Post.title.name, "title")
	assert_that(Post.attrs["title"] is Post.title)


def test_assigns_model_attr():
	class Post(Model):
		title = attr(str)

	created = Store().create(Post, title="Intro")
	created.title = "Revised"

	assert_eq(created.title, "Revised")


def test_inherits_model_attrs():
	class Content(Model):
		title = attr(str)

	class Post(Content):
		body = attr(str)

	created = Store().create(Post, title="Intro", body="Welcome")

	assert_that(Post.title is not None)
	assert_that(Post.body is not None)
	assert_eq(created.title, "Intro")
	assert_eq(created.body, "Welcome")


def test_doesnt_inherit_from_multiple_model_classes():
	class Content(Model):
		pass

	class Publishable(Model):
		pass

	with assert_raises(ModelError):

		class Post(Content, Publishable):
			pass


def test_overrides_inherited_model_attr():
	class Content(Model):
		score = attr(str)

	class Post(Content):
		score = attr(int)

	created = Store().create(Post, score=3)

	assert_eq(created.score, 3)


def test_doesnt_replace_inherited_attr_with_non_attribute():
	class Content(Model):
		title = attr(str)

	with assert_raises(ModelError):

		class Post(Content):
			title = "Intro"


def test_rejects_attrs_declaration():
	with assert_raises(ModelError):

		class Post(Model):
			attrs = ()


def test_creates_model_with_default_attr():
	class Post(Model):
		unread = attr(bool, default=True)

	store = Store()

	created = store.create(Post)

	assert_eq(created.unread, True)


def test_doesnt_create_model_with_missing_attr():
	class Post(Model):
		title = attr(str)

	store = Store()

	with assert_raises(ModelError):
		store.create(Post)


def test_doesnt_create_model_with_extra_attr():
	class Post(Model):
		pass

	store = Store()

	with assert_raises(ModelError):
		store.create(Post, title="Intro")


def test_doesnt_create_model_with_null_attr():
	class Post(Model):
		title = attr(str)

	store = Store()

	with assert_raises(ModelError):
		store.create(Post, title=None)


def test_finds_all_models():
	class Post(Model):
		pass

	store = Store()
	store.create(Post)
	store.create(Post)

	found = store.find_all(Post)

	assert_eq(len(found), 2)


def test_finds_one_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	found = store.find_one(Post, created.id)

	assert_eq(found.id, created.id)


def test_find_one_raises_when_model_doesnt_exist():
	class Post(Model):
		pass

	store = Store()
	id = uuid4()

	with assert_raises(NotFoundError) as raised:
		store.find_one(Post, id)

	assert_that(raised.exception.model_type is Post)
	assert_eq(raised.exception.id, id)


def test_find_one_raises_when_model_has_wrong_type():
	class User(Model):
		pass

	class Post(Model):
		pass

	store = Store()
	user = store.create(User)

	with assert_raises(NotFoundError):
		store.find_one(Post, user.id)


def test_finds_model_by_attrs():
	class User(Model):
		admin = attr(bool)

	store = Store()
	store.create(User, admin=False)
	store.create(User, admin=False)
	store.create(User, admin=True)

	found = store.find_by(User, admin=False)

	assert_eq(len(found), 2)


def test_finds_model_by_conjunction():
	class User(Model):
		name = attr(str)
		admin = attr(bool)

	store = Store()
	store.create(User, name="Alice", admin=False)
	store.create(User, name="Bob", admin=False)
	store.create(User, name="Clyde", admin=True)

	found = store.find_by(User, name="Clyde", admin=True)

	assert_eq(len(found), 1)


def test_deletes_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	store.delete(Post, created.id)
	found = store.find_all(Post)

	assert_eq(len(found), 0)


def test_encodes_and_decodes_store():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.id, created.id)
	assert_eq(encode(decoded), encoded)
	assert_eq(list(encoded[0]), ["_type", "id", "created_at"])


def test_encodes_and_decodes_attrs_with_simple_types():
	class Post(Model):
		title = attr(str)

	store = Store()
	created = store.create(Post, title="Intro")

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.id, created.id)
	assert_eq(found.created_at, created.created_at)
	assert_eq(found.title, created.title)


def test_encodes_and_decodes_integer_attrs():
	class Post(Model):
		points = attr(int)

	store = Store()
	created = store.create(Post, points=3)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.points, created.points)


def test_encodes_and_decodes_attrs_with_complex_types():
	class Post(Model):
		author_id = attr(UUID)

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_encodes_and_decodes_nullable_attrs_when_present():
	class Post(Model):
		author_id = attr(UUID, nullable=True)

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_encodes_and_decodes_nullable_attrs_when_absent():
	class Post(Model):
		author_id = attr(UUID, nullable=True)

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, None)
