from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import parser
from helios.form.field import Field
from helios.form.parser import ParseError
from helios.http import Input


def test_requires_fields_without_defaults():
	assert_that(Field("title", parser.Str()).required)
	assert_that(not Field("title", parser.Str(), "").required)


def test_absent_values_are_missing():
	field = Field("title", parser.Str())

	assert_that(field.missing(Input()))


def test_blank_strings_are_missing():
	field = Field("title", parser.Str())

	assert_that(field.missing(Input({"title": ""})))
	assert_that(field.missing(Input({"title": " \t\n"})))
	assert_that(not field.missing(Input({"title": " Intro "})))


def test_lists_are_missing_only_when_nothing_was_sent():
	field = Field("tags", parser.List(parser.Str()))

	assert_that(field.missing(Input()))
	assert_that(field.missing(Input({"tags": []})))
	assert_that(not field.missing(Input({"tags": ""})))
	assert_that(not field.missing(Input({"tags": ["", " "]})))


def test_parses_the_sent_value():
	board_id = uuid4()
	field = Field("board_ids", parser.List(parser.UUID()), [])

	assert_eq(field.parse(Input({"board_ids": [str(board_id)]})), [board_id])


def test_raises_parse_errors():
	field = Field("page_size", parser.Int(), 20)

	with assert_raises(ParseError):
		field.parse(Input({"page_size": "many"}))


def test_copies_the_default():
	default = []
	field = Field("tags", parser.List(parser.Str()), default)

	assert_eq(field.initial, [])
	assert_that(field.initial is not default)
