from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import parser
from helios.form.parser import ParseError

def test_parses_strings_without_coercion():
	value_parser = parser.Str()

	assert_eq(value_parser.parse("title"), "title")
	assert_parse_error(value_parser, ["first", "second"], "must be a single value")


def test_parses_uuid():
	value_parser = parser.UUID()
	raw = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"

	assert_eq(value_parser.parse(raw), UUID(raw))
	assert_parse_error(value_parser, "not-a-uuid", "must be a valid UUID")


def test_parses_required_value():
	value_parser = parser.Required(parser.Str())

	assert_eq(value_parser.parse("title"), "title")
	assert_parse_error(value_parser, None, "must be provided")
	assert_parse_error(value_parser, "", "must not be empty")


def test_parses_optional_blank_and_value():
	value_parser = parser.Optional(parser.UUID())
	raw = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"

	assert_that(value_parser.parse("") is None)
	assert_eq(value_parser.parse(raw), UUID(raw))
	assert_parse_error(value_parser, [raw], "must be a single value")


def test_parses_checked_boolean_strictly():
	value_parser = parser.Bool()

	assert_that(value_parser.parse("on") is True)
	assert_parse_error(value_parser, "true", 'must be "on" or omitted')
	assert_parse_error(value_parser, ["on"], 'must be "on" or omitted')


def test_parses_list_from_scalar_and_list():
	value_parser = parser.List(parser.UUID())
	first = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	second = "f262c72c-92e8-4e1f-9644-b1d24afad614"

	assert_eq(value_parser.parse(first), [UUID(first)])
	assert_eq(value_parser.parse([first, second]), [UUID(first), UUID(second)])


def test_list_preserves_item_parse_error():
	value_parser = parser.List(parser.UUID())

	assert_parse_error(value_parser, ["not-a-uuid"], "must be a valid UUID")


def assert_parse_error(value_parser, value, message):
	with assert_raises(ParseError) as raised:
		value_parser.parse(value)

	assert_eq(str(raised.exception), message)
