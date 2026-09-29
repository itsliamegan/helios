from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.database import Config, DatabaseError, Model, ModelError, Store
from helios.database.sqlite import connect


class Item(Model):
	table = "items"

	name: str
	group: str | None = None
	rank: int


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
				set(names(store.query(Item).where({"group": "one"}).all())),
				{"Alpha", "Beta"},
			)
			assert_eq(
				set(names(store.query(Item).where({"group =": "one"}).all())),
				{"Alpha", "Beta"},
			)
			assert_eq(
				names(store.query(Item).where({"group": "one", "rank": 1}).all()),
				["Beta"],
			)
			assert_eq(
				names(
					store.query(Item).where({"group": "one"}).where({"rank": 1}).all()
				),
				["Beta"],
			)
			assert_eq(
				store.query(Item).where({"rank": 1}).where({"rank": 2}).all(),
				[],
			)
			assert_eq(names(store.query(Item).where({"group": None}).all()), ["Gamma"])
		finally:
			connection.close()


def test_filters_by_comparison_operators():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				names(store.query(Item).where({"rank <": 2}).all()),
				["Beta"],
			)
			assert_eq(
				set(names(store.query(Item).where({"rank <=": 2}).all())),
				{"Alpha", "Beta"},
			)
			assert_eq(
				names(store.query(Item).where({"rank >": 2}).all()),
				["Gamma"],
			)
			assert_eq(
				set(names(store.query(Item).where({"rank >=": 2}).all())),
				{"Alpha", "Gamma"},
			)
			assert_eq(
				set(names(store.query(Item).where({"rank >=": 1, "rank <": 3}).all())),
				{"Alpha", "Beta"},
			)
		finally:
			connection.close()


def test_where_any_joins_groups_with_or():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				set(
					names(
						store.query(Item)
						.where_any({"group": "one", "rank": 1}, {"rank >": 2})
						.all()
					)
				),
				{"Beta", "Gamma"},
			)
			assert_eq(
				names(
					store.query(Item)
					.where({"group": "one"})
					.where_any({"rank": 2}, {"rank": 3})
					.all()
				),
				["Alpha"],
			)
		finally:
			connection.close()


def test_where_not_is_the_exact_complement_of_where():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			everything = set(names(store.query(Item).all()))
			for conditions in (
				{"group <": "two"},
				{"group": "one", "rank": 1},
				{"group in": ["one"]},
			):
				kept = set(names(store.query(Item).where(conditions).all()))
				dropped = set(names(store.query(Item).where_not(conditions).all()))

				assert_eq(kept & dropped, set())
				assert_eq(kept | dropped, everything)
			assert_eq(
				names(store.query(Item).where_not({"group <": "two"}).all()),
				["Gamma"],
			)
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
			assert_that(store.query(Item).where({"name": "missing"}).first() is None)
			assert_that(store.query(Item).limit(0).first() is None)
		finally:
			connection.close()


def test_derived_queries_are_independent_and_reusable():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			base = store.query(Item).where({"group": "one"})
			first = base.order_by("rank").limit(1)
			second = base.order_by("rank", "desc").limit(2)

			assert_eq(names(first.all()), ["Beta"])
			assert_eq(names(second.all()), ["Alpha", "Beta"])
			assert_eq(set(names(base.all())), {"Alpha", "Beta"})
			assert_eq(names(first.all()), ["Beta"])
		finally:
			connection.close()


def test_binds_sql_looking_filter_values_as_data():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			value = "Alpha' OR 1 = 1 --"
			store.create(Item, name=value, group="two", rank=4)

			assert_eq(names(store.query(Item).where({"name": value}).all()), [value])
		finally:
			connection.close()


def test_in_matches_membership():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			alpha = store.find_by(Item, {"name": "Alpha"})[0]
			gamma = store.find_by(Item, {"name": "Gamma"})[0]
			assert_eq(
				set(
					names(
						store.query(Item).where({"id in": [alpha.id, gamma.id]}).all()
					)
				),
				{"Alpha", "Gamma"},
			)
		finally:
			connection.close()


def test_in_combines_with_other_conditions_using_and():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				names(
					store.query(Item).where({"group": "one", "rank in": [1, 3]}).all()
				),
				["Beta"],
			)
			assert_eq(
				names(
					store.query(Item)
					.where({"rank in": [1, 2]})
					.where({"rank in": [2, 3]})
					.all()
				),
				["Alpha"],
			)
		finally:
			connection.close()


def test_in_works_with_order_by_limit_and_first():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			ranked = store.query(Item).where({"rank in": [1, 2, 3]}).order_by("rank")
			assert_eq(names(ranked.all()), ["Beta", "Alpha", "Gamma"])
			assert_eq(names(ranked.limit(2).all()), ["Beta", "Alpha"])
			assert_eq(ranked.first().name, "Beta")
		finally:
			connection.close()


def test_in_with_an_empty_iterable_matches_nothing():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(store.query(Item).where({"rank in": []}).all(), [])
		finally:
			connection.close()


def test_in_with_a_none_member_includes_null_rows():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			assert_eq(
				set(names(store.query(Item).where({"group in": ["one", None]}).all())),
				{"Alpha", "Beta", "Gamma"},
			)
			assert_eq(
				names(store.query(Item).where({"group in": [None]}).all()),
				["Gamma"],
			)
		finally:
			connection.close()


def test_in_consumes_a_generator_once_and_stays_reusable():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			query = store.query(Item).where({"rank in": (rank for rank in (1, 2))})
			assert_eq(set(names(query.all())), {"Alpha", "Beta"})
			assert_eq(set(names(query.all())), {"Alpha", "Beta"})
		finally:
			connection.close()


def test_in_binds_sql_looking_values_as_data():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			value = "Alpha' OR 1 = 1 --"
			store.create(Item, name=value, group="two", rank=4)

			assert_eq(
				names(store.query(Item).where({"name in": [value]}).all()),
				[value],
			)
		finally:
			connection.close()


def test_rejects_malformed_condition_keys():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			for key in ("rank  >", " rank", "rank > 1", "", 1):
				with assert_raises(ModelError) as raised:
					store.query(Item).where({key: 1})
				assert_eq(
					str(raised.exception),
					f"Query on Item has {key!r}, which is not a condition key",
				)
		finally:
			connection.close()


def test_rejects_unknown_operators():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError) as raised:
				store.query(Item).where({"rank !=": 1})
			assert_eq(
				str(raised.exception),
				"Query on Item has 'rank !=', which has an unknown operator",
			)
		finally:
			connection.close()


def test_rejects_invalid_values():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			cases = [
				({"rank": True}, "'rank': expected an integer, got bool"),
				({"rank >": None}, "'rank >': cannot compare with None"),
				({"name": None}, "'name': cannot be null"),
				(
					{"rank in": 1},
					"'rank in': expected an iterable other than str or bytes, got int",
				),
				(
					{"name in": "Alpha"},
					"'name in': expected an iterable other than str or bytes, got str",
				),
				({"rank in": [True]}, "'rank in': expected an integer, got bool"),
				({"rank in": [None]}, "'rank in': cannot be null"),
			]
			for conditions, message in cases:
				with assert_raises(ModelError) as raised:
					store.query(Item).where(conditions)
				assert_eq(
					str(raised.exception),
					f"Query on Item has an invalid value for {message}",
				)
		finally:
			connection.close()


def test_rejects_empty_condition_groups():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			query = store.query(Item)
			for build in (
				lambda: query.where({}),
				lambda: query.where_not({}),
				lambda: query.where_any({}),
			):
				with assert_raises(ModelError) as raised:
					build()
				assert_eq(
					str(raised.exception),
					"Query on Item has an empty condition group",
				)
		finally:
			connection.close()


def test_rejects_where_any_with_no_groups():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError) as raised:
				store.query(Item).where_any()
			assert_eq(
				str(raised.exception),
				"Query on Item has where_any with no groups",
			)
		finally:
			connection.close()


def test_rejects_conditions_that_are_not_dictionaries():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError) as raised:
				store.query(Item).where([("rank", 1)])
			assert_eq(
				str(raised.exception),
				"Query on Item takes a dictionary of conditions, got list",
			)
			with assert_raises(ModelError) as raised:
				store.query(Item).where_any({"rank": 1}, [])
			assert_eq(
				str(raised.exception),
				"Query on Item takes a dictionary of conditions, got list",
			)
		finally:
			connection.close()


def test_rejects_unknown_attributes():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ModelError):
				store.query(Item).where({"missing": 1})
			with assert_raises(ModelError):
				store.query(Item).where({"group.name": "one"})
			with assert_raises(ModelError):
				store.query(Item).order_by("missing")
		finally:
			connection.close()


def test_rejects_invalid_order_and_limit():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			with assert_raises(ValueError):
				store.query(Item).order_by("name", "sideways")
			with assert_raises(ValueError):
				store.query(Item).limit(-1)
			with assert_raises(ValueError):
				store.query(Item).limit(True)
		finally:
			connection.close()


def test_raw_select_preserves_order():
	with TemporaryDirectory() as directory:
		connection, store = open_store(Path(directory, "app.sqlite"))
		try:
			alpha = store.find_by(Item, {"name": "Alpha"})[0]
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

			assert_eq([item.id for item in selected], [alpha.id])
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
