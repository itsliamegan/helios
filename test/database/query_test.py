from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Config, DatabaseError, Model, ModelError, Store, attribute
from helios.database.sqlite import connect


class Item(Model):
	table = "items"

	name = attribute(str)
	group = attribute(str, nullable=True)
	rank = attribute(int)


SCHEMA = """
CREATE TABLE items (
	id TEXT PRIMARY KEY,
	created_at TEXT NOT NULL,
	name TEXT NOT NULL,
	"group" TEXT,
	rank INTEGER NOT NULL
);
CREATE TABLE labels (
	item_id TEXT NOT NULL REFERENCES items (id),
	name TEXT NOT NULL
);
"""


def open_store(path: Path):
	raw = sqlite3.connect(path, autocommit=True)
	raw.executescript(SCHEMA)
	raw.close()
	connection = connect(Config(path))
	connection.begin()
	store = Store(connection, [Item])
	store.create(Item, name="Alpha", group="one", rank=2)
	store.create(Item, name="Beta", group="one", rank=1)
	store.create(Item, name="Gamma", group=None, rank=3)
	return connection, store


def names(items: list[Item]) -> list[str]:
	return [item.name for item in items]


def test_filters_by_equality_conjunction_and_null():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				set(names(store.query(Item).where(group="one").all())),
				{"Alpha", "Beta"},
			)
			assert_eq(
				names(store.query(Item).where(group="one").where(rank=1).all()),
				["Beta"],
			)
			assert_eq(
				store.query(Item).where(rank=1).where(rank=2).all(),
				[],
			)
			assert_eq(names(store.query(Item).where(group=None).all()), ["Gamma"])
		finally:
			connection.close()


def test_orders_limits_and_finds_first():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			ascending = store.query(Item).order_by("rank").all()
			descending = store.query(Item).order_by("rank", "desc").all()

			assert_eq(names(ascending), ["Beta", "Alpha", "Gamma"])
			assert_eq(names(descending), ["Gamma", "Alpha", "Beta"])
			assert_eq(
				names(store.query(Item).order_by("rank").limit(2).all()),
				["Beta", "Alpha"],
			)
			assert_eq(store.query(Item).limit(0).all(), [])
			assert_eq(store.query(Item).order_by("rank").first().name, "Beta")
			assert_that(store.query(Item).where(name="missing").first() is None)
			assert_that(store.query(Item).limit(0).first() is None)
		finally:
			connection.close()


def test_derived_queries_are_independent_and_reusable():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			base = store.query(Item).where(group="one")
			first = base.order_by("rank").limit(1)
			second = base.order_by("rank", "desc").limit(2)

			assert_eq(names(first.all()), ["Beta"])
			assert_eq(names(second.all()), ["Alpha", "Beta"])
			assert_eq(set(names(base.all())), {"Alpha", "Beta"})
			assert_eq(names(first.all()), ["Beta"])

			replaced = first.order_by("name", "desc").limit(2)
			assert_eq(names(replaced.all()), ["Beta", "Alpha"])
			assert_eq(names(first.all()), ["Beta"])
		finally:
			connection.close()


def test_rejects_invalid_query_construction_before_execution():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError):
				store.query(Item).where(missing="value")
			with assert_raises(ModelError):
				store.query(Item).order_by("missing")
			with assert_raises(ValueError):
				store.query(Item).order_by("name", "sideways")
			with assert_raises(ValueError):
				store.query(Item).limit(-1)
			with assert_raises(ValueError):
				store.query(Item).limit(True)
			with assert_raises(ModelError):
				store.query(Item).where(rank=True)
		finally:
			connection.close()


def test_binds_sql_looking_filter_values_as_data():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			value = "Alpha' OR 1 = 1 --"
			store.create(Item, name=value, group="two", rank=4)

			assert_eq(names(store.query(Item).where(name=value).all()), [value])
		finally:
			connection.close()


def test_where_in_matches_membership():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			alpha = store.find_by(Item, name="Alpha")[0]
			gamma = store.find_by(Item, name="Gamma")[0]
			assert_eq(
				set(names(store.query(Item).where_in(id=[alpha.id, gamma.id]).all())),
				{"Alpha", "Gamma"},
			)
		finally:
			connection.close()


def test_where_in_combines_with_where_and_where_in_using_and():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				names(store.query(Item).where(group="one").where_in(rank=[1, 3]).all()),
				["Beta"],
			)
			assert_eq(
				names(
					store.query(Item).where_in(rank=[1, 2]).where_in(rank=[2, 3]).all()
				),
				["Alpha"],
			)
		finally:
			connection.close()


def test_where_in_works_with_order_by_limit_and_first():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			ordered = store.query(Item).where_in(rank=[1, 2, 3]).order_by("rank").all()
			assert_eq(names(ordered), ["Beta", "Alpha", "Gamma"])
			assert_eq(
				names(
					store.query(Item)
					.where_in(rank=[1, 2, 3])
					.order_by("rank")
					.limit(2)
					.all()
				),
				["Beta", "Alpha"],
			)
			assert_eq(
				store.query(Item)
				.where_in(rank=[1, 2, 3])
				.order_by("rank")
				.first()
				.name,
				"Beta",
			)
		finally:
			connection.close()


def test_where_in_empty_iterable_matches_nothing():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(store.query(Item).where_in(rank=[]).all(), [])
		finally:
			connection.close()


def test_where_in_none_among_candidates_includes_null_row():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				set(names(store.query(Item).where_in(group=["one", None]).all())),
				{"Alpha", "Beta", "Gamma"},
			)
			assert_eq(
				names(store.query(Item).where_in(group=[None]).all()),
				["Gamma"],
			)
		finally:
			connection.close()


def test_where_in_consumes_generator_once_and_stays_reusable():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			query = store.query(Item).where_in(rank=(rank for rank in (1, 2)))
			assert_eq(set(names(query.all())), {"Alpha", "Beta"})
			assert_eq(set(names(query.all())), {"Alpha", "Beta"})
		finally:
			connection.close()


def test_where_in_rejects_invalid_construction_before_execution():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError):
				store.query(Item).where_in(missing=["value"])
			with assert_raises(ModelError):
				store.query(Item).where_in(rank=[True])
			with assert_raises(ModelError):
				store.query(Item).where_in(rank=[None])
			with assert_raises(TypeError):
				store.query(Item).where_in(name="Alpha")
		finally:
			connection.close()


def test_where_in_binds_sql_looking_candidate_values_as_data():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			value = "Alpha' OR 1 = 1 --"
			store.create(Item, name=value, group="two", rank=4)

			assert_eq(
				names(store.query(Item).where_in(name=[value]).all()),
				[value],
			)
		finally:
			connection.close()


def test_raw_select_preserves_order_and_identity():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			alpha = store.find_by(Item, name="Alpha")[0]
			connection.execute(
				"INSERT INTO labels (item_id, name) VALUES (?, ?)",
				(str(alpha.id), "featured"),
			).close()
			selected = store.select(
				Item,
				"""
				SELECT items.* FROM items
				JOIN labels ON labels.item_id = items.id
				WHERE labels.name = ?
				ORDER BY items.rank DESC
				""",
				("featured",),
			)

			assert_eq(selected, [alpha])
			assert_that(selected[0] is alpha)
		finally:
			connection.close()


def test_raw_select_rejects_malformed_shape_and_value():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(DatabaseError):
				store.select(Item, "SELECT items.*, 1 AS extra FROM items", ())
			with assert_raises(DatabaseError):
				store.select(
					Item,
					"SELECT id, created_at, name, \"group\", 'bad' AS rank FROM items",
					(),
				)
		finally:
			connection.close()
