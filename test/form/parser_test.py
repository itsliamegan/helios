from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import RuleError, parser
from helios.http import URL


def test_parses_strings_without_coercion():
	value_parser = parser.Str()

	assert_eq(value_parser.check("title"), "title")
	assert_check_error(value_parser, ["first", "second"], "must be a single value")


def test_parses_integers():
	value_parser = parser.Int()

	assert_eq(value_parser.check("42"), 42)
	assert_eq(value_parser.check("-3"), -3)
	assert_check_error(value_parser, "4.5", None)
	assert_check_error(value_parser, "1_000", None)


def test_parses_uuid():
	value_parser = parser.UUID()
	board_id = uuid4()

	assert_eq(value_parser.check(str(board_id)), board_id)
	assert_check_error(value_parser, "not-a-uuid", None)
	assert_check_error(value_parser, [str(board_id)], "must be a single value")


def test_parses_url():
	value_parser = parser.URL()
	raw = "https://example.com:8443/search?q=today"

	value = value_parser.check(raw)
	assert_that(isinstance(value, URL))
	assert_eq(str(value), raw)
	assert_check_error(value_parser, "https://example.com:invalid", None)


def test_parses_checked_boolean_strictly():
	value_parser = parser.Bool()

	assert_that(value_parser.check("on") is True)
	assert_check_error(value_parser, "true", None)
	assert_check_error(value_parser, ["on"], None)


def test_parses_list_from_scalar_and_list():
	value_parser = parser.List(parser.UUID())
	first_board_id = uuid4()
	second_board_id = uuid4()

	assert_eq(value_parser.check(str(first_board_id)), [first_board_id])
	assert_eq(
		value_parser.check([str(first_board_id), str(second_board_id)]),
		[first_board_id, second_board_id],
	)


def test_list_takes_name_and_message_from_items():
	value_parser = parser.List(parser.UUID())

	assert_eq(value_parser.name, "uuid")
	assert_eq(value_parser.message, "must be a valid UUID")
	assert_check_error(value_parser, ["not-a-uuid"], None)


def test_names_parsers_with_default_messages():
	assert_eq(
		[
			(value_parser.name, value_parser.message)
			for value_parser in [
				parser.Str(),
				parser.Int(),
				parser.UUID(),
				parser.URL(),
				parser.Bool(),
			]
		],
		[
			("string", "must be a single value"),
			("integer", "must be a whole number"),
			("uuid", "must be a valid UUID"),
			("url", "must be a valid URL"),
			("boolean", 'must be "on" or omitted'),
		],
	)


def assert_check_error(value_parser, value, message):
	with assert_raises(RuleError) as raised:
		value_parser.check(value)

	assert_eq(raised.exception.message, message)
