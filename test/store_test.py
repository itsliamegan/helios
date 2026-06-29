from lux.store import decode, encode, types, Attribute, Model, ModelError, Schema, Store

from uuid import uuid4

def test_creates_model_with_builtin_attrs():
	class Post(Model):
		pass

	store = Store()

	created = store.create(Post)

	assert created.id is not None
	assert created.created_at is not None

def test_creates_model_with_attr():
	class Post(Model):
		attrs = [
			Attribute("title", types.Str())
		]

	store = Store()

	created = store.create(Post, title = "Intro")

	assert created.title == "Intro"

def test_creates_model_with_compound_attr():
	class Post(Model):
		attrs = [
			Attribute("tags", types.List(types.Str()))
		]

	store = Store()

	created = store.create(Post, tags = ["news"])

	assert created.tags == ["news"]

def test_creates_model_with_default_attr():
	class Post(Model):
		attrs = [
			Attribute("unread", types.Bool(), default = True)
		]

	store = Store()

	created = store.create(Post)

	assert created.unread == True

def test_doesnt_create_model_with_missing_attr():
	class Post(Model):
		attrs = [
			Attribute("title", types.Str())
		]

	store = Store()

	try:
		store.create(Post)
		assert False, "should throw ModelError"
	except ModelError:
		assert True

def test_doesnt_create_model_with_extra_attr():
	class Post(Model):
		attrs = []

	store = Store()

	try:
		store.create(Post, title = "Intro")
		assert False, "should throw ModelError"
	except ModelError:
		assert True

def test_doesnt_create_model_with_null_attr():
	class Post(Model):
		attrs = [
			Attribute("title", types.Str())
		]

	store = Store()

	try:
		store.create(Post, title = None)
		assert False, "should throw ModelError"
	except ModelError:
		assert True

def test_finds_all_models():
	class Post(Model):
		pass

	store = Store()
	store.create(Post)
	store.create(Post)

	found = store.find_all(Post)

	assert len(found) == 2

def test_finds_one_model():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	found = store.find_one(Post, created.id)

	assert found.id == created.id

def test_finds_model_by_attrs():
	class User(Model):
		attrs = [
			Attribute("admin", types.Bool())
		]

	store = Store()
	store.create(User, admin = False)
	store.create(User, admin = False)
	store.create(User, admin = True)

	found = store.find_by(User, admin = False)

	assert len(found) == 2

def test_encodes_and_decodes_store():
	class Post(Model):
		pass

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.id == created.id

def test_encodes_and_decodes_attrs_with_simple_types():
	class Post(Model):
		attrs = [
			Attribute("title", types.Str())
		]

	store = Store()
	created = store.create(Post, title = "Intro")

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.id == created.id
	assert found.created_at == created.created_at
	assert found.title == created.title

def test_encodes_and_decodes_attrs_with_complex_types():
	class Post(Model):
		attrs = [
			Attribute("author_id", types.UUID())
		]

	store = Store()
	created = store.create(Post, author_id = uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.author_id == created.author_id

def test_encodes_and_decodes_attrs_with_compound_types():
	class Post(Model):
		attrs = [
			Attribute("backlink_ids", types.List(types.UUID()))
		]

	store = Store()
	created = store.create(Post, backlink_ids = [uuid4()])

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.backlink_ids == created.backlink_ids

def test_encodes_and_decodes_nullable_attrs_when_present():
	class Post(Model):
		attrs = [
			Attribute("author_id", types.UUID(), nullable = True)
		]

	store = Store()
	created = store.create(Post, author_id = uuid4())

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.author_id == created.author_id

def test_encodes_and_decodes_nullable_attrs_when_absent():
	class Post(Model):
		attrs = [
			Attribute("author_id", types.UUID(), nullable = True)
		]

	store = Store()
	created = store.create(Post)

	encoded = encode(store)
	decoded = decode(encoded, Schema([Post]))
	found = decoded.find_one(Post, created.id)

	assert found.author_id == None
