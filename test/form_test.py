from typing import ClassVar
from uuid import UUID, uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import Errors, Filters, Form, FormError, RuleError, Rules, Untrimmed
from helios.form.filter import Compact, Unspace, Upcase
from helios.form.rule import Distinct, Length
from helios.http import Input, URL


class PinForm(Form):
	title: str
	note: Untrimmed = Untrimmed("")
	board_ids: list[UUID] = []
	return_to: str | None = None


def test_validates_annotated_fields():
	read_later_id = uuid4()
	inbox_id = uuid4()
	form, errors = PinForm.validate(
		Input(
			{
				"title": "Intro",
				"note": "Read later",
				"board_ids": [str(read_later_id), str(inbox_id)],
				"return_to": "/boards",
			}
		)
	)

	assert_eq(errors, Errors())
	assert_eq(form.title, "Intro")
	assert_eq(form.note, "Read later")
	assert_eq(form.board_ids, [read_later_id, inbox_id])
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

	first.board_ids.append(uuid4())

	assert_eq(second.board_ids, [])
	assert_eq(PinForm(title="Intro").board_ids, [])


def test_requires_fields_without_defaults():
	form, errors = PinForm.validate(Input())

	assert_eq(errors.messages["title"], ["Title must be provided."])
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

	assert_eq(errors.messages["title"], ["Title must be provided."])
	assert_that(form.return_to is None)


def test_trims_list_items_and_keeps_blank_ones():
	class TagsForm(Form):
		tags: list[str] = []

	form, errors = TagsForm.validate(Input({"tags": [" design ", " ", ""]}))

	assert_that(not errors)
	assert_eq(form.tags, ["design", "", ""])


def test_trims_padded_list_items_before_parsing():
	board_id = uuid4()
	form, errors = PinForm.validate(
		Input({"title": "Intro", "board_ids": [f" {board_id} "]})
	)

	assert_that(not errors)
	assert_eq(form.board_ids, [board_id])


def test_keeps_untrimmed_fields_exactly_as_sent():
	class PasswordForm(Form):
		password: Untrimmed

	indented, _ = PinForm.validate(Input({"title": "Intro", "note": "  - item\n"}))
	padded, padded_errors = PasswordForm.validate(Input({"password": " secret "}))

	assert_eq(indented.note, "  - item\n")
	assert_that(not padded_errors)
	assert_eq(padded.password, " secret ")


def test_treats_blank_untrimmed_fields_as_missing():
	class PasswordForm(Form):
		password: Untrimmed

	_, blank_errors = PasswordForm.validate(Input({"password": "   "}))
	_, missing_errors = PasswordForm.validate(Input())

	assert_eq(blank_errors.messages["password"], ["Password must be provided."])
	assert_eq(missing_errors.messages["password"], ["Password must be provided."])


def test_records_parse_errors_with_readable_field_names():
	form, errors = PinForm.validate(Input({"title": "Intro", "return_to": ["/", "/"]}))

	assert_eq(form.title, "Intro")
	assert_eq(errors.messages, {"return_to": ["Return to must be a single value."]})


def test_words_list_item_parse_errors_as_items():
	board_id = uuid4()
	_, errors = PinForm.validate(
		Input({"title": "Intro", "board_ids": [str(board_id), "not-a-uuid"]})
	)

	assert_eq(
		errors.messages,
		{"board_ids": ["An item in board ids must be a valid UUID."]},
	)


def test_rejects_repeated_scalar_values():
	_, errors = PinForm.validate(Input({"title": ["Intro", "Outro"]}))

	assert_eq(errors.messages["title"], ["Title must be a single value."])


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
	board_id = uuid4()
	form = PinForm(title="Intro", board_ids=[board_id])

	assert_eq(form.title, "Intro")
	assert_eq(form.note, "")
	assert_eq(form.board_ids, [board_id])
	assert_that(form.return_to is None)


def test_construction_rejects_missing_and_extra_fields():
	with assert_raises(TypeError) as missing:
		PinForm()  # ty: ignore[missing-argument]
	with assert_raises(TypeError) as extra:
		PinForm(title="Intro", body="Hello")  # ty: ignore[unknown-argument]

	assert_eq(str(missing.exception), "PinForm is missing fields: title")
	assert_eq(str(extra.exception), "PinForm got unexpected fields: body")


def test_rejects_subclassing_a_form():
	with assert_raises(FormError):

		class ArchivablePinForm(PinForm):
			archived: bool = False


def test_ignores_class_variables():
	class NoteForm(Form):
		limit: ClassVar[int] = 10

		body: str

	assert_eq(list(NoteForm.fields), ["body"])


def test_rejects_unsupported_field_types():
	with assert_raises(FormError) as raised:

		class BadForm(Form):
			tags: dict[str, str]

	assert_eq(
		str(raised.exception),
		"BadForm.tags: unsupported field type: dict[str, str]",
	)


def test_rejects_string_annotations():
	with assert_raises(FormError):

		class BadForm(Form):
			title: "str"  # noqa: UP037


def test_rejects_undefined_annotations():
	with assert_raises(FormError):

		class BadForm(Form):
			board: Board  # noqa: F821


def test_rejects_field_names_form_uses():
	with assert_raises(FormError) as raised:

		class BadForm(Form):
			values: str

	assert_eq(
		str(raised.exception),
		"Form BadForm has a field named 'values', which Form uses",
	)


class WebURL:
	name = "web_url"

	def check(self, value: str):
		if not value.startswith(("http://", "https://")):
			raise RuleError("must start with http:// or https://")


def test_runs_rules_on_parsed_values():
	class LinkForm(Form):
		rules = Rules({"url": [WebURL()], "board_ids": [Distinct()]})

		url: str
		board_ids: list[UUID] = []

	read_later_id = uuid4()
	inbox_id = uuid4()
	form, errors = LinkForm.validate(
		Input(
			{
				"url": "https://example.com",
				"board_ids": [str(read_later_id), str(inbox_id)],
			}
		)
	)
	_, invalid_errors = LinkForm.validate(
		Input({"url": "example.com", "board_ids": [str(inbox_id), str(inbox_id)]})
	)

	assert_that(not errors)
	assert_eq(form.url, "https://example.com")
	assert_eq(
		invalid_errors.messages,
		{
			"url": ["Url must start with http:// or https://."],
			"board_ids": ["Board ids must not repeat a value."],
		},
	)


def test_overrides_messages_by_field_and_rule():
	class LinkForm(Form):
		rules = Rules({"url": [WebURL()]})
		messages = {
			"title.required": "Give the pin a title.",
			"url.web_url": "Use a web address.",
			"board_ids.invalid": "Choose boards from the list.",
		}

		title: str
		url: str
		board_ids: list[UUID] = []

	_, errors = LinkForm.validate(
		Input({"url": "example.com", "board_ids": "not-a-uuid"})
	)

	assert_eq(
		errors.messages,
		{
			"title": ["Give the pin a title."],
			"url": ["Use a web address."],
			"board_ids": ["Choose boards from the list."],
		},
	)


def test_rejects_rules_for_undeclared_fields():
	with assert_raises(FormError) as raised:

		class LinkForm(Form):
			rules = Rules({"link": [WebURL()]})

			url: str

	assert_eq(
		str(raised.exception),
		"Form LinkForm has rules for 'link', which is not a field",
	)


def test_applies_filters_before_rules():
	class SignInForm(Form):
		filters = Filters({"recovery_code": [Unspace(), Upcase()]})
		rules = Rules({"recovery_code": [Length(exactly=8)]})

		recovery_code: str

	form, errors = SignInForm.validate(Input({"recovery_code": " abcd efgh "}))

	assert_that(not errors)
	assert_eq(form.recovery_code, "ABCDEFGH")


def test_applies_item_filters_and_rules():
	class TagsForm(Form):
		filters = Filters({"tags.*": [Upcase()], "tags": [Compact()]})
		rules = Rules({"tags.*": [Length(maximum=5)], "tags": [Distinct()]})

		tags: list[str] = []

	form, errors = TagsForm.validate(Input({"tags": [" art ", "", "news"]}))
	_, item_errors = TagsForm.validate(Input({"tags": ["art", "reading"]}))
	_, list_errors = TagsForm.validate(Input({"tags": ["art", "ART"]}))

	assert_that(not errors)
	assert_eq(form.tags, ["ART", "NEWS"])
	assert_eq(
		item_errors.messages,
		{"tags": ["An item in tags must be at most 5 characters."]},
	)
	assert_eq(list_errors.messages, {"tags": ["Tags must not repeat a value."]})


def test_overrides_item_messages_by_items_key():
	class TagsForm(Form):
		rules = Rules(
			{
				"tag_names.*": [Length(maximum=5)],
				"tag_names": [Length(maximum=1)],
			}
		)
		messages = {
			"tag_names.*.length": "Tags must be at most 5 characters.",
			"tag_names.length": "Choose one tag.",
		}

		tag_names: list[str] = []

	_, item_errors = TagsForm.validate(Input({"tag_names": ["reading"]}))
	_, list_errors = TagsForm.validate(Input({"tag_names": ["art", "news"]}))

	assert_eq(
		item_errors.messages,
		{"tag_names": ["Tags must be at most 5 characters."]},
	)
	assert_eq(list_errors.messages, {"tag_names": ["Choose one tag."]})


def test_overrides_item_parse_messages_by_invalid_key():
	class BoardsForm(Form):
		messages = {
			"board_ids.*.invalid": "Unused.",
			"board_ids.invalid": "Choose boards from the list.",
		}

		board_ids: list[UUID] = []

	_, errors = BoardsForm.validate(Input({"board_ids": ["not-a-uuid"]}))

	assert_eq(errors.messages, {"board_ids": ["Choose boards from the list."]})


def test_rejects_filters_for_undeclared_fields():
	with assert_raises(FormError) as raised:

		class SignInForm(Form):
			filters = Filters({"code": [Upcase()]})

			recovery_code: str

	assert_eq(
		str(raised.exception),
		"Form SignInForm has filters for 'code', which is not a field",
	)


def test_rejects_item_keys_for_undeclared_fields():
	with assert_raises(FormError) as raised:

		class TagsForm(Form):
			rules = Rules({"labels.*": [Length(maximum=5)]})

			tags: list[str] = []

	assert_eq(
		str(raised.exception),
		"Form TagsForm has rules for 'labels', which is not a field",
	)


def test_rejects_item_keys_for_fields_that_are_not_lists():
	with assert_raises(FormError) as raised:

		class SignInForm(Form):
			filters = Filters({"recovery_code.*": [Upcase()]})

			recovery_code: str

	assert_eq(
		str(raised.exception),
		"Form SignInForm has filters for 'recovery_code.*', "
		"but 'recovery_code' is not a list",
	)


class Recorded:
	name = "recorded"

	def __init__(self):
		self.values = []

	def apply(self, value: object) -> object:
		self.values.append(value)
		return value

	def check(self, value: object):
		self.values.append(value)


def test_skips_filters_and_rules_for_missing_optional_fields():
	recorded = Recorded()

	class TagsForm(Form):
		filters = Filters({"tags.*": [recorded], "tags": [recorded]})
		rules = Rules({"tags.*": [recorded], "tags": [recorded]})

		tags: list[str] = ["default"]

	form, errors = TagsForm.validate(Input())

	assert_that(not errors)
	assert_eq(form.tags, ["default"])
	assert_eq(recorded.values, [])


def test_skips_filters_and_rules_after_a_parse_error():
	recorded = Recorded()

	class BoardsForm(Form):
		filters = Filters({"board_ids": [recorded]})
		rules = Rules({"board_ids": [recorded]})

		board_ids: list[UUID] = []

	_, errors = BoardsForm.validate(Input({"board_ids": ["not-a-uuid"]}))

	assert_that("board_ids" in errors)
	assert_eq(recorded.values, [])


class Failing:
	def apply(self, value: str) -> str:
		raise RuleError("must not be filtered")


def test_propagates_rule_errors_raised_outside_rules():
	class NoteForm(Form):
		filters = Filters({"body": [Failing()]})

		body: str

	with assert_raises(RuleError):
		NoteForm.validate(Input({"body": "Hello"}))


def test_controllers_add_their_own_errors():
	form, errors = PinForm.validate(Input({"title": "Intro"}))

	if form.title == "Intro":
		errors.add("title", "That title is taken.")

	assert_eq(errors.messages, {"title": ["That title is taken."]})
