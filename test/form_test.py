from typing import ClassVar
from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import Errors, Form, Verbatim
from helios.http import Input, URL

FIRST_ID = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
SECOND_ID = "f262c72c-92e8-4e1f-9644-b1d24afad614"


class PinForm(Form):
	title: str
	note: Verbatim = Verbatim("")
	board_ids: list[UUID] = []
	return_to: str | None = None


def test_validates_annotated_fields():
	form, errors = PinForm.validate(
		Input(
			{
				"title": "Intro",
				"note": "Read later",
				"board_ids": [FIRST_ID, SECOND_ID],
				"return_to": "/boards",
			}
		)
	)

	assert_eq(errors, Errors())
	assert_eq(form.title, "Intro")
	assert_eq(form.note, "Read later")
	assert_eq(form.board_ids, [UUID(FIRST_ID), UUID(SECOND_ID)])
	assert_eq(form.return_to, "/boards")


def test_fills_missing_optional_fields_with_defaults():
	form, errors = PinForm.validate(Input({"title": "Intro"}))

	assert_that(not errors)
	assert_eq(form.note, "")
	assert_eq(form.board_ids, [])
	assert_that(form.return_to is None)


def test_copies_mutable_defaults():
	first, _ = PinForm.validate(Input({"title": "Intro"}))
	second, _ = PinForm.validate(Input({"title": "Intro"}))

	first.board_ids.append(UUID(FIRST_ID))

	assert_eq(second.board_ids, [])
	assert_eq(PinForm(title="Intro").board_ids, [])


def test_requires_fields_without_defaults():
	form, errors = PinForm.validate(Input())

	assert_eq(errors["title"], ["Title must be provided."])
	with assert_raises(AttributeError) as raised:
		_ = form.title
	assert_eq(str(raised.exception), "PinForm.title has not been initialized")


def test_trims_strings():
	form, errors = PinForm.validate(
		Input({"title": "  Intro  ", "return_to": "  /boards "})
	)

	assert_that(not errors)
	assert_eq(form.title, "Intro")
	assert_eq(form.return_to, "/boards")


def test_treats_blank_strings_as_missing():
	form, errors = PinForm.validate(Input({"title": "   ", "return_to": ""}))

	assert_eq(errors["title"], ["Title must be provided."])
	assert_that(form.return_to is None)


def test_trims_list_items_and_drops_blank_ones():
	form, errors = PinForm.validate(
		Input({"title": "Intro", "board_ids": [f" {FIRST_ID} ", " ", ""]})
	)

	assert_that(not errors)
	assert_eq(form.board_ids, [UUID(FIRST_ID)])


def test_keeps_verbatim_fields_exactly_as_sent():
	class PasswordForm(Form):
		password: Verbatim

	indented, _ = PinForm.validate(Input({"title": "Intro", "note": "  - item\n"}))
	blank, blank_errors = PasswordForm.validate(Input({"password": ""}))
	_, missing_errors = PasswordForm.validate(Input())

	assert_eq(indented.note, "  - item\n")
	assert_that(not blank_errors)
	assert_eq(blank.password, "")
	assert_eq(missing_errors["password"], ["Password must be provided."])


def test_records_parse_errors_with_readable_field_names():
	form, errors = PinForm.validate(
		Input({"title": "Intro", "board_ids": [FIRST_ID, "not-a-uuid"]})
	)

	assert_eq(form.title, "Intro")
	assert_eq(errors.messages, {"board_ids": ["Board ids must be a valid UUID."]})


def test_rejects_repeated_scalar_values():
	_, errors = PinForm.validate(Input({"title": ["Intro", "Outro"]}))

	assert_eq(errors["title"], ["Title must be a single value."])


def test_parses_checkboxes_and_other_scalar_types():
	class SettingsForm(Form):
		open_in_new_tab: bool = False
		page_size: int = 20
		homepage: URL | None = None

	checked, checked_errors = SettingsForm.validate(
		Input(
			{
				"open_in_new_tab": "on",
				"page_size": "50",
				"homepage": "https://example.com",
			}
		)
	)
	unchecked, _ = SettingsForm.validate(Input())
	_, invalid_errors = SettingsForm.validate(
		Input({"open_in_new_tab": "yes", "page_size": "many"})
	)

	assert_that(not checked_errors)
	assert_that(checked.open_in_new_tab is True)
	assert_eq(checked.page_size, 50)
	assert_eq(str(checked.homepage), "https://example.com")
	assert_that(unchecked.open_in_new_tab is False)
	assert_eq(unchecked.page_size, 20)
	assert_eq(
		invalid_errors.messages,
		{
			"open_in_new_tab": ['Open in new tab must be "on" or omitted.'],
			"page_size": ["Page size must be a whole number."],
		},
	)


def test_constructs_with_fields():
	form = PinForm(title="Intro", board_ids=[UUID(FIRST_ID)])

	assert_eq(form.title, "Intro")
	assert_eq(form.note, "")
	assert_eq(form.board_ids, [UUID(FIRST_ID)])
	assert_that(form.return_to is None)


def test_construction_rejects_missing_and_extra_fields():
	with assert_raises(TypeError) as missing:
		PinForm()  # ty: ignore[missing-argument]
	with assert_raises(TypeError) as extra:
		PinForm(title="Intro", body="Hello")  # ty: ignore[unknown-argument]

	assert_eq(str(missing.exception), "PinForm is missing fields: title")
	assert_eq(str(extra.exception), "PinForm got unexpected fields: body")


def test_subclasses_inherit_fields():
	class ArchivablePinForm(PinForm):
		archived: bool = False

	form, errors = ArchivablePinForm.validate(
		Input({"title": "Intro", "archived": "on"})
	)

	assert_that(not errors)
	assert_eq(form.title, "Intro")
	assert_that(form.archived is True)


def test_ignores_class_variables():
	class NoteForm(Form):
		limit: ClassVar[int] = 10

		body: str

	assert_eq(list(NoteForm.fields), ["body"])


def test_rejects_unsupported_field_types():
	with assert_raises(TypeError) as raised:

		class BadForm(Form):
			tags: dict[str, str]

	assert_eq(
		str(raised.exception),
		"BadForm.tags: unsupported field type: dict[str, str]",
	)


def test_rejects_field_names_form_uses():
	with assert_raises(TypeError) as raised:

		class BadForm(Form):
			values: str

	assert_eq(
		str(raised.exception),
		'BadForm has a field named "values", which Form uses',
	)
