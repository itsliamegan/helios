from uuid import UUID

from luna.test.assertion import assert_eq

from helios.form import Field, Form, parser
from helios.http import Input


def test_validates_required_when_provided():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input({"title": "Intro"}))

	assert_eq(input, {"title": "Intro"})
	assert_eq(errs, {})


def test_validates_required_when_missing():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input())

	assert_eq(input, {})
	assert_eq(errs, {"title": ["must be provided"]})


def test_validates_required_when_empty():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input({"title": ""}))

	assert_eq(input, {})
	assert_eq(errs, {"title": ["must not be empty"]})


def test_parses_uuid():
	raw = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	form = Form([Field("user_id", parser.UUID())])

	data, errors = form.validate(Input({"user_id": raw}))

	assert_eq(data, {"user_id": UUID(raw)})
	assert_eq(errors, {})


def test_custom_parser_can_handle_missing_input():
	class DefaultParser:
		def parse(self, value: str | list[str] | None) -> str:
			if value is None:
				return "default"
			if isinstance(value, list):
				raise parser.ParseError("must be a single value")
			return value

	form = Form([Field("value", DefaultParser())])

	data, errors = form.validate(Input())

	assert_eq(data, {"value": "default"})
	assert_eq(errors, {})


def test_records_parse_errors():
	form = Form([Field("user_id", parser.UUID())])

	data, errors = form.validate(Input({"user_id": "not-a-uuid"}))

	assert_eq(data, {})
	assert_eq(errors, {"user_id": ["must be a valid UUID"]})


def test_parses_missing_optional_boolean_and_list_fields():
	form = Form(
		[
			Field("parent_id", parser.Optional(parser.UUID())),
			Field("archived", parser.Bool()),
			Field("user_id", parser.List(parser.UUID())),
		]
	)

	data, errors = form.validate(Input())

	assert_eq(data, {"parent_id": None, "archived": False, "user_id": []})
	assert_eq(errors, {})


def test_parses_list_uuid_field_from_browser_input():
	first = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	second = "f262c72c-92e8-4e1f-9644-b1d24afad614"
	form = Form([Field("user_id", parser.List(parser.UUID()))])

	scalar, scalar_errors = form.validate(Input({"user_id": first}))
	repeated, repeated_errors = form.validate(Input({"user_id": [first, second]}))

	assert_eq(scalar, {"user_id": [UUID(first)]})
	assert_eq(scalar_errors, {})
	assert_eq(repeated, {"user_id": [UUID(first), UUID(second)]})
	assert_eq(repeated_errors, {})


def test_parses_checkbox_presence():
	form = Form([Field("archived", parser.Bool())])

	checked, checked_errors = form.validate(Input({"archived": "on"}))
	unexpected, unexpected_errors = form.validate(Input({"archived": "yes"}))

	assert_eq(checked, {"archived": True})
	assert_eq(checked_errors, {})
	assert_eq(unexpected, {})
	assert_eq(unexpected_errors, {"archived": ['must be "on" or omitted']})
