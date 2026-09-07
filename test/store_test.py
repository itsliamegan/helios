from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.store import (
	Attribute,
	Model,
	ModelError,
	NotFoundError,
	Schema,
	Store,
	decode,
	encode,
	types,
)


def test_creates_model_with_builtin_attrs():
	class Post(Model):
		pass

	store = Store()

	created = store.create(Post)

	assert_that(created.id is not None)
	assert_that(created.created_at is not None)


def test_creates_model_with_attr():
	class Post(Model):
		attrs = [Attribute("title", types.Str())]

	store = Store()

	created = store.create(Post, title="Intro")

	assert_eq(created.title, "Intro")


def test_creates_model_with_compound_attr():
	class Post(Model):
		attrs = [Attribute("tags", types.List(types.Str()))]

	store = Store()

	created = store.create(Post, tags=["news"])

	assert_eq(created.tags, ["news"])


def test_creates_model_with_default_attr():
	class Post(Model):
		attrs = [Attribute("unread", types.Bool(), default=True)]

	store = Store()

	created = store.create(Post)

	assert_eq(created.unread, True)


def test_doesnt_create_model_with_missing_attr():
	class Post(Model):
		attrs = [Attribute("title", types.Str())]

	store = Store()

	with assert_raises(ModelError):
		store.create(Post)


def test_doesnt_create_model_with_extra_attr():
	class Post(Model):
		attrs = []

	store = Store()

	with assert_raises(ModelError):
		store.create(Post, title="Intro")


def test_doesnt_create_model_with_null_attr():
	class Post(Model):
		attrs = [Attribute("title", types.Str())]

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
		attrs = [Attribute("admin", types.Bool())]

	store = Store()
	store.create(User, admin=False)
	store.create(User, admin=False)
	store.create(User, admin=True)

	found = store.find_by(User, admin=False)

	assert_eq(len(found), 2)


def test_finds_model_by_conjunction():
	class User(Model):
		attrs = [
			Attribute("name", types.Str()),
			Attribute("admin", types.Bool()),
		]

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


def test_encodes_and_decodes_attrs_with_simple_types():
	class Post(Model):
		attrs = [Attribute("title", types.Str())]

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
		attrs = [Attribute("points", types.Int())]

	store = Store()
	created = store.create(Post, points=3)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.points, created.points)


def test_encodes_and_decodes_attrs_with_complex_types():
	class Post(Model):
		attrs = [Attribute("author_id", types.UUID())]

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_encodes_and_decodes_attrs_with_compound_types():
	class Post(Model):
		attrs = [Attribute("backlink_ids", types.List(types.UUID()))]

	store = Store()
	created = store.create(Post, backlink_ids=[uuid4()])

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.backlink_ids, created.backlink_ids)


def test_encodes_and_decodes_nullable_attrs_when_present():
	class Post(Model):
		attrs = [Attribute("author_id", types.UUID(), nullable=True)]

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_encodes_and_decodes_nullable_attrs_when_absent():
	class Post(Model):
		attrs = [Attribute("author_id", types.UUID(), nullable=True)]

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, None)
