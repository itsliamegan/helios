from uuid import UUID

from helios.form import Field, Form, parser
from helios.http import Input


def test_validates_required_when_provided():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input({"title": "Intro"}))

	assert input == {"title": "Intro"}
	assert errs == {}


def test_validates_required_when_missing():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input())

	assert input == {}
	assert errs == {"title": ["must be provided"]}


def test_validates_required_when_empty():
	form = Form([Field("title", parser.Required(parser.Str()))])

	input, errs = form.validate(Input({"title": ""}))

	assert input == {}
	assert errs == {"title": ["must not be empty"]}


def test_parses_uuid():
	raw = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	form = Form([Field("user_id", parser.UUID())])

	data, errors = form.validate(Input({"user_id": raw}))

	assert data == {"user_id": UUID(raw)}
	assert errors == {}


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

	assert data == {"value": "default"}
	assert errors == {}


def test_records_parse_errors():
	form = Form([Field("user_id", parser.UUID())])

	data, errors = form.validate(Input({"user_id": "not-a-uuid"}))

	assert data == {}
	assert errors == {"user_id": ["must be a valid UUID"]}


def test_parses_missing_optional_boolean_and_list_fields():
	form = Form(
		[
			Field("parent_id", parser.Optional(parser.UUID())),
			Field("archived", parser.Bool()),
			Field("user_id", parser.List(parser.UUID())),
		]
	)

	data, errors = form.validate(Input())

	assert data == {"parent_id": None, "archived": False, "user_id": []}
	assert errors == {}


def test_parses_list_uuid_field_from_browser_input():
	first = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
	second = "f262c72c-92e8-4e1f-9644-b1d24afad614"
	form = Form([Field("user_id", parser.List(parser.UUID()))])

	scalar, scalar_errors = form.validate(Input({"user_id": first}))
	repeated, repeated_errors = form.validate(Input({"user_id": [first, second]}))

	assert scalar == {"user_id": [UUID(first)]}
	assert scalar_errors == {}
	assert repeated == {"user_id": [UUID(first), UUID(second)]}
	assert repeated_errors == {}


def test_parses_checkbox_presence():
	form = Form([Field("archived", parser.Bool())])

	checked, checked_errors = form.validate(Input({"archived": "on"}))
	unexpected, unexpected_errors = form.validate(Input({"archived": "yes"}))

	assert checked == {"archived": True}
	assert checked_errors == {}
	assert unexpected == {}
	assert unexpected_errors == {"archived": ['must be "on" or omitted']}
