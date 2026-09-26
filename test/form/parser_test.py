from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import parser
from helios.form.parser import ParseError
from helios.http import URL


def test_parses_strings_without_coercion():
	value_parser = parser.Str()

	assert_eq(value_parser.parse("title"), "title")
	assert_parse_error(value_parser, ["first", "second"], "must be a single value")


def test_strings_keep_surrounding_whitespace():
	value_parser = parser.Str()

	assert_eq(value_parser.parse("  - item\n"), "  - item\n")


def test_parses_integers():
	value_parser = parser.Int()

	assert_eq(value_parser.parse("42"), 42)
	assert_eq(value_parser.parse("-3"), -3)
	assert_eq(value_parser.parse(" 42 "), 42)
	assert_parse_error(value_parser, "4.5", "must be a whole number")
	assert_parse_error(value_parser, "1_000", "must be a whole number")


def test_parses_uuid():
	value_parser = parser.UUID()
	board_id = uuid4()

	assert_eq(value_parser.parse(str(board_id)), board_id)
	assert_eq(value_parser.parse(f" {board_id}\n"), board_id)
	assert_parse_error(value_parser, "not-a-uuid", "must be a valid UUID")
	assert_parse_error(value_parser, [str(board_id)], "must be a single value")


def test_parses_url():
	value_parser = parser.URL()
	raw = "https://example.com:8443/search?q=today"

	value = value_parser.parse(raw)
	padded = value_parser.parse(f"  {raw} ")
	assert_that(isinstance(value, URL))
	assert_eq(str(value), raw)
	assert_eq(str(padded), raw)
	assert_parse_error(
		value_parser,
		"https://example.com:invalid",
		"must be a valid URL",
	)


def test_parses_checked_boolean_strictly():
	value_parser = parser.Bool()

	assert_that(value_parser.parse("on") is True)
	assert_that(value_parser.parse(" on ") is True)
	assert_parse_error(value_parser, "true", 'must be "on" or omitted')
	assert_parse_error(value_parser, ["on"], 'must be "on" or omitted')


def test_parses_list_from_scalar_and_list():
	value_parser = parser.List(parser.UUID())
	first_board_id = uuid4()
	second_board_id = uuid4()

	assert_eq(value_parser.parse(str(first_board_id)), [first_board_id])
	assert_eq(
		value_parser.parse([str(first_board_id), str(second_board_id)]),
		[first_board_id, second_board_id],
	)


def test_list_records_that_an_item_failed():
	value_parser = parser.List(parser.UUID())

	with assert_raises(ParseError) as raised:
		value_parser.parse([str(uuid4()), "not-a-uuid"])

	assert_eq(raised.exception.message, "must be a valid UUID")
	assert_that(raised.exception.item)


def test_scalar_parse_errors_are_not_item_errors():
	with assert_raises(ParseError) as raised:
		parser.UUID().parse("not-a-uuid")

	assert_that(not raised.exception.item)


def assert_parse_error(value_parser, value, message):
	with assert_raises(ParseError) as raised:
		value_parser.parse(value)

	assert_eq(raised.exception.message, message)
