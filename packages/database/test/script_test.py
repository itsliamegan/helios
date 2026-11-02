from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

from helios.database.error import ScriptError
from helios.database.script import Script


def test_splits_statements_at_their_semicolons():
	with TemporaryDirectory() as directory:
		path = Path(directory, "schema.sql")
		path.write_text(
			"CREATE TABLE posts (id INTEGER);\nCREATE TABLE tags (id INTEGER);\n"
		)

		script = Script.read(path)

	assert_eq(
		[statement.sql for statement in script.statements],
		["CREATE TABLE posts (id INTEGER);\n", "CREATE TABLE tags (id INTEGER);\n"],
	)


def test_keeps_semicolons_inside_strings_in_one_statement():
	with TemporaryDirectory() as directory:
		path = Path(directory, "schema.sql")
		path.write_text("INSERT INTO posts VALUES ('a;\nb');\n")

		script = Script.read(path)

	assert_eq(
		[statement.sql for statement in script.statements],
		["INSERT INTO posts VALUES ('a;\nb');\n"],
	)


def test_keeps_a_trigger_body_in_one_statement():
	with TemporaryDirectory() as directory:
		path = Path(directory, "schema.sql")
		path.write_text(
			"CREATE TRIGGER posts_comment AFTER INSERT ON posts\n"
			"BEGIN\n"
			"\tINSERT INTO comments VALUES ('posted');\n"
			"END;\n"
		)

		script = Script.read(path)

	assert_eq(len(script.statements), 1)


def test_skips_statements_that_hold_only_comments():
	with TemporaryDirectory() as directory:
		path = Path(directory, "schema.sql")
		path.write_text(
			"-- Posts.\nCREATE TABLE posts (id INTEGER);\n/* trailing comment */\n;\n"
		)

		script = Script.read(path)

	assert_eq(
		[statement.sql for statement in script.statements],
		["-- Posts.\nCREATE TABLE posts (id INTEGER);\n"],
	)


def test_refuses_an_incomplete_final_statement():
	with TemporaryDirectory() as directory:
		path = Path(directory, "schema.sql")
		path.write_text(
			"CREATE TABLE posts (id INTEGER);\nCREATE TABLE tags (id INTEGER)\n"
		)

		with assert_raises(ScriptError):
			Script.read(path)
