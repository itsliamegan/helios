from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import Compact, Length, Only, RuleError, Unspace, Upcase, parser
from helios.form.field import Failure, Field
from helios.http import Input


class Suffix:
	def __init__(self, text: str):
		self.text = text

	def apply(self, value: str) -> str:
		return value + self.text


class WebURL:
	name = "web_url"

	def check(self, value: str):
		if not value.startswith(("http://", "https://")):
			raise RuleError("must start with http:// or https://")


class Refuses:
	def __init__(self, name: str, refused: str):
		self.name = name
		self.refused = refused

	def check(self, value: str):
		if value == self.refused:
			raise RuleError(f"must not be {self.refused}")


class Recorded:
	name = "recorded"

	def __init__(self):
		self.values = []

	def check(self, value: object):
		self.values.append(value)


def test_returns_the_parsed_value():
	field = Field("title", parser.Str())

	assert_eq(field.validate(Input({"title": "Intro"})), "Intro")


def test_requires_fields_without_defaults():
	field = Field("title", parser.Str())

	failure = failure_of(field, Input())

	assert_eq((failure.key, failure.item), ("required", False))
	assert_eq(failure.message, "must be provided")


def test_treats_whitespace_only_strings_as_missing():
	required = Field("title", parser.Str())
	optional = Field("return_to", parser.Str(), None)
	input = Input({"title": " \t\n", "return_to": ""})

	failure = failure_of(required, input)

	assert_eq(failure.key, "required")
	assert_that(optional.validate(input) is None)
	assert_eq(input.items, {"title": " \t\n", "return_to": ""})


def test_trims_strings_by_default():
	field = Field("title", parser.Str())

	assert_eq(field.validate(Input({"title": "  Intro \n"})), "Intro")


def test_untrimmed_fields_keep_their_padding():
	field = Field("note", parser.Str(), "", True)

	assert_eq(field.validate(Input({"note": "  - item\n"})), "  - item\n")


def test_untrimmed_fields_treat_whitespace_only_as_missing():
	field = Field("password", parser.Str(), untrimmed=True)

	failure = failure_of(field, Input({"password": "   "}))

	assert_eq(failure.key, "required")


def test_keeps_blank_list_items_and_trims_the_rest():
	field = Field("tags", parser.List(parser.Str()), [])

	assert_eq(field.validate(Input({"tags": [" a ", ""]})), ["a", ""])
	assert_eq(field.validate(Input({"tags": ""})), [""])


def test_lists_are_missing_only_when_nothing_was_sent():
	field = Field("tags", parser.List(parser.Str()))

	absent = failure_of(field, Input())
	empty = failure_of(field, Input({"tags": []}))

	assert_eq(absent.key, "required")
	assert_eq(empty.key, "required")


def test_runs_filters_in_declared_order():
	field = Field("code", parser.Str(), filters=[Suffix("a"), Upcase(), Suffix("b")])

	assert_eq(field.validate(Input({"code": "x"})), "XAb")


def test_runs_filters_before_rules():
	field = Field(
		"code",
		parser.Str(),
		filters=[Unspace(), Upcase()],
		rules=[Only("ABCD"), Length(exactly=4)],
	)

	assert_eq(field.validate(Input({"code": "ab cd"})), "ABCD")


def test_runs_rules_in_declared_order():
	field = Field(
		"handle",
		parser.Str(),
		rules=[Refuses("reserved", "admin"), Refuses("taken", "admin")],
	)

	failure = failure_of(field, Input({"handle": "admin"}))

	assert_eq(failure.key, "reserved")
	assert_eq(failure.message, "must not be admin")


def test_stops_at_the_first_failing_rule():
	recorded = Recorded()
	field = Field("url", parser.Str(), rules=[WebURL(), recorded])

	failure = failure_of(field, Input({"url": "example.com"}))

	assert_eq((failure.key, failure.item), ("web_url", False))
	assert_eq(failure.message, "must start with http:// or https://")
	assert_eq(recorded.values, [])


def test_runs_item_filters_before_list_filters():
	field = Field(
		"tags",
		parser.List(parser.Str()),
		item_filters=[Suffix("!")],
		filters=[Compact()],
	)

	assert_eq(field.validate(Input({"tags": ["a", ""]})), ["a!", "!"])


def test_runs_item_rules_before_list_rules():
	field = Field(
		"tags",
		parser.List(parser.Str()),
		item_rules=[Length(maximum=3)],
		rules=[Length(maximum=1)],
	)

	failure = failure_of(field, Input({"tags": ["a", "long"]}))

	assert_eq((failure.key, failure.item), ("length", True))
	assert_eq(failure.message, "must be at most 3 characters")


def test_reports_list_rule_failures_as_field_failures():
	field = Field("tags", parser.List(parser.Str()), rules=[Length(maximum=1)])

	failure = failure_of(field, Input({"tags": ["a", "b"]}))

	assert_eq((failure.key, failure.item), ("length", False))
	assert_eq(failure.message, "must have at most 1 item")


def test_stops_at_the_first_failing_item():
	recorded = Recorded()
	field = Field(
		"tags",
		parser.List(parser.Str()),
		item_rules=[recorded, Refuses("reserved", "admin")],
	)

	failure = failure_of(field, Input({"tags": ["design", "admin", "art"]}))

	assert_eq(failure.key, "reserved")
	assert_eq(recorded.values, ["design", "admin"])


def test_skips_everything_for_missing_optional_fields():
	recorded = Recorded()
	field = Field(
		"tags",
		parser.List(parser.Str()),
		["default"],
		item_filters=[Suffix("!")],
		filters=[Compact()],
		item_rules=[recorded],
		rules=[recorded],
	)

	assert_eq(field.validate(Input()), ["default"])
	assert_eq(recorded.values, [])


def test_copies_the_default_of_a_missing_optional_field():
	default = []
	field = Field("tags", parser.List(parser.Str()), default)

	value = field.validate(Input())

	assert_eq(value, [])
	assert_that(value is not default)


def test_reports_parse_failures_as_invalid():
	field = Field("page_size", parser.Int(), 20)

	failure = failure_of(field, Input({"page_size": "many"}))

	assert_eq((failure.key, failure.item), ("invalid", False))
	assert_eq(failure.message, "must be a whole number")


def test_reports_list_item_parse_failures_as_invalid_items():
	recorded = Recorded()
	field = Field(
		"board_ids",
		parser.List(parser.UUID()),
		[],
		item_rules=[recorded],
		rules=[recorded],
	)

	failure = failure_of(field, Input({"board_ids": [str(uuid4()), "not-a-uuid"]}))

	assert_eq((failure.key, failure.item), ("invalid", True))
	assert_eq(failure.message, "must be a valid UUID")
	assert_eq(recorded.values, [])


def failure_of(field, input):
	with assert_raises(Failure) as raised:
		field.validate(input)

	return raised.exception
