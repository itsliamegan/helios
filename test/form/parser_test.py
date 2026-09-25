from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import parser
from helios.form.parser import ParseError
from helios.http import URL


def test_parses_strings_without_coercion():
	value_parser = parser.Str()

	assert_eq(value_parser.parse("title"), "title")
	assert_parse_error(
		value_parser, ["first", "second"], "string", "must be a single value"
	)


def test_parses_integers():
	value_parser = parser.Int()

	assert_eq(value_parser.parse("42"), 42)
	assert_eq(value_parser.parse("-3"), -3)
	assert_parse_error(value_parser, "4.5", "integer", "must be a whole number")
	assert_parse_error(value_parser, "1_000", "integer", "must be a whole number")


def test_parses_uuid():
	value_parser = parser.UUID()
	raw = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"

	assert_eq(value_parser.parse(raw), UUID(raw))
	assert_parse_error(value_parser, "not-a-uuid", "uuid", "must be a valid UUID")
	assert_parse_error(value_parser, [raw], "uuid", "must be a single value")


def test_parses_url():
	value_parser = parser.URL()
	raw = "https://example.com:8443/search?q=today"

	value = value_parser.parse(raw)
	assert_that(isinstance(value, URL))
	assert_eq(str(value), raw)
	assert_parse_error(
		value_parser, "https://example.com:invalid", "url", "must be a valid URL"
	)


def test_parses_checked_boolean_strictly():
	value_parser = parser.Bool()

	assert_that(value_parser.parse("on") is True)
	assert_parse_error(value_parser, "true", "boolean", 'must be "on" or omitted')
	assert_parse_error(value_parser, ["on"], "boolean", 'must be "on" or omitted')


def test_parses_list_from_scalar_and_list():
	value_parser = parser.List(parser.UUID())
	first = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	second = "f262c72c-92e8-4e1f-9644-b1d24afad614"

	assert_eq(value_parser.parse(first), [UUID(first)])
	assert_eq(value_parser.parse([first, second]), [UUID(first), UUID(second)])


def test_list_preserves_item_parse_error():
	value_parser = parser.List(parser.UUID())

	assert_parse_error(value_parser, ["not-a-uuid"], "uuid", "must be a valid UUID")


def assert_parse_error(value_parser, value, rule, message):
	with assert_raises(ParseError) as raised:
		value_parser.parse(value)

	assert_eq(raised.exception.rule, rule)
	assert_eq(str(raised.exception), message)
