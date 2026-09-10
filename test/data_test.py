from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.data.model import Model, ModelError, attr
from helios.data.store import NotFoundError, Schema, Store, decode, encode


def test_creates_model():
	class Post(Model):
		title = attr(str)

	store = Store()
	created = store.create(Post, title="Intro")

	assert_eq(created.title, "Intro")
	assert_that(created.created_at is not None)
	assert_that(store.find_one(Post, created.id) is created)


def test_encodes_created_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, created.id).id, created.id)


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


def test_find_one_rejects_missing_model():
	class Post(Model):
		pass

	store = Store()
	id = uuid4()

	with assert_raises(NotFoundError):
		store.find_one(Post, id)


def test_find_one_rejects_wrong_type():
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


def test_saves_new_model():
	class Post(Model):
		pass

	new = Post()
	store = Store()

	store.save(new)
	created_at = new.created_at
	store.save(new)

	assert_that(created_at is not None)
	assert_eq(new.created_at, created_at)
	assert_that(store.find_one(Post, new.id) is new)


def test_rejects_replacement():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)
	replacement = Post()
	replacement.id = created.id

	with assert_raises(ModelError):
		store.save(replacement)


def test_saves_existing_model():
	class Post(Model):
		title = attr(str)

	store = Store()
	saved = store.create(Post, title="Intro")
	saved.title = "Revised"

	store.save(saved)
	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, saved.id).title, "Revised")


def test_ignores_unsaved_change():
	class Post(Model):
		title = attr(str)

	store = Store()
	created = store.create(Post, title="Intro")

	created.title = "Revised"
	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, created.id).title, "Intro")


def test_saves_selected_model():
	class Post(Model):
		title = attr(str)

	store = Store()
	first = store.create(Post, title="First")
	second = store.create(Post, title="Second")
	first.title = "Saved"
	second.title = "Not saved"

	store.save(first)
	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, first.id).title, "Saved")
	assert_eq(persisted.find_one(Post, second.id).title, "Second")


def test_saves_multiple_models():
	class Post(Model):
		title = attr(str)

	store = Store()
	first = store.create(Post, title="First")
	second = store.create(Post, title="Second")
	first.title = "First revised"
	second.title = "Second revised"

	store.save(first)
	store.save(second)
	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, first.id).title, "First revised")
	assert_eq(persisted.find_one(Post, second.id).title, "Second revised")


def test_save_snapshots_values():
	class Post(Model):
		title = attr(str)

	store = Store()
	saved = store.create(Post, title="Intro")
	saved.title = "Saved"
	store.save(saved)
	saved.title = "Not saved"

	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, saved.id).title, "Saved")


def test_later_save_wins():
	class Post(Model):
		title = attr(str)

	store = Store()
	saved = store.create(Post, title="Intro")
	saved.title = "First revision"
	store.save(saved)
	saved.title = "Second revision"
	store.save(saved)

	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_one(Post, saved.id).title, "Second revision")


def test_omits_unsaved_model():
	class Post(Model):
		pass

	store = Store()
	Post()

	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_all(Post), [])


def test_removes_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	store.delete(created.id)
	found = store.find_all(Post)

	assert_eq(len(found), 0)


def test_deletes_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	store.delete(created.id)
	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_all(Post), [])


def test_delete_overrides_save():
	class Post(Model):
		title = attr(str)

	store = Store()
	saved = store.create(Post, title="Intro")
	saved.title = "Revised"
	store.save(saved)
	store.delete(saved.id)

	persisted = decode(encode(store), Schema([Post]))

	assert_eq(persisted.find_all(Post), [])


def test_round_trips_store():
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


def test_round_trips_string_attr():
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


def test_round_trips_integer_attr():
	class Post(Model):
		points = attr(int)

	store = Store()
	created = store.create(Post, points=3)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.points, created.points)


def test_round_trips_uuid_attr():
	class Post(Model):
		author_id = attr(UUID)

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_round_trips_nullable_attr():
	class Post(Model):
		author_id = attr(UUID, nullable=True)

	store = Store()
	created = store.create(Post, author_id=uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, created.author_id)


def test_round_trips_null_attr():
	class Post(Model):
		author_id = attr(UUID, nullable=True)

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert_eq(found.author_id, None)
