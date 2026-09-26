from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises

from helios.declarative import MISSING
from helios.form import Distinct, Length, Only, RuleError, parser
from helios.form.form import Failure, Field
from helios.http import Input


def test_names_built_in_rules():
	assert_eq(
		[Length(exactly=1).name, Only("ab").name, Distinct().name],
		["length", "only", "distinct"],
	)


def test_length_accepts_values_within_its_limits():
	Length(exactly=4).check("ABCD")
	Length(minimum=3).check("abc")
	Length(maximum=3).check("abc")
	Length(minimum=1, maximum=3).check(["design", "reading"])
	Length(maximum=0).check([])


def test_length_rejects_strings_by_character_count():
	assert_rule_error(Length(exactly=10), "short", "must be 10 characters")
	assert_rule_error(Length(minimum=3), "ab", "must be at least 3 characters")
	assert_rule_error(Length(maximum=200), "a" * 201, "must be at most 200 characters")
	assert_rule_error(
		Length(minimum=3, maximum=20),
		"ab",
		"must be between 3 and 20 characters",
	)
	assert_rule_error(
		Length(minimum=3, maximum=20),
		"a" * 21,
		"must be between 3 and 20 characters",
	)


def test_length_rejects_lists_by_item_count():
	assert_rule_error(Length(exactly=10), ["a"], "must have 10 items")
	assert_rule_error(Length(minimum=3), ["a", "b"], "must have at least 3 items")
	assert_rule_error(Length(maximum=2), ["a", "b", "c"], "must have at most 2 items")
	assert_rule_error(
		Length(minimum=3, maximum=20),
		[],
		"must have between 3 and 20 items",
	)


def test_length_uses_a_singular_unit_for_a_limit_of_one():
	assert_rule_error(Length(exactly=1), "ab", "must be 1 character")
	assert_rule_error(Length(minimum=1), "", "must be at least 1 character")
	assert_rule_error(Length(maximum=1), ["a", "b"], "must have at most 1 item")


def test_length_requires_a_limit():
	with assert_raises(TypeError):
		Length()


def test_length_rejects_exactly_with_a_bound():
	with assert_raises(TypeError):
		Length(exactly=3, minimum=1)
	with assert_raises(TypeError):
		Length(exactly=3, maximum=5)


def test_length_rejects_a_minimum_above_its_maximum():
	with assert_raises(TypeError):
		Length(minimum=5, maximum=3)


def test_only_checks_the_characters_of_a_string():
	rule = Only("ABCDEF")

	rule.check("FACADE")
	rule.check("")
	assert_rule_error(rule, "FACADE1", "must only contain allowed characters")
	assert_rule_error(rule, "AB CD", "must only contain allowed characters")


def test_only_checks_the_items_of_a_list():
	rule = Only(["design", "reading"])

	rule.check(["reading", "design", "reading"])
	assert_rule_error(rule, ["design", "art"], "must only contain allowed items")


def test_only_compares_whole_items_of_a_list():
	rule = Only("ABC")

	assert_rule_error(rule, ["AB"], "must only contain allowed items")


def test_distinct_rejects_repeated_items():
	board_id = uuid4()
	rule = Distinct()

	rule.check([board_id, uuid4()])
	rule.check([])
	assert_rule_error(rule, [board_id, board_id], "must not repeat a value")


def assert_rule_error(rule, value, message):
	with assert_raises(RuleError) as raised:
		rule.check(value)

	assert_eq(raised.exception.message, message)


class WebURL:
	name = "web_url"

	def check(self, value: str):
		if not value.startswith(("http://", "https://")):
			raise RuleError("must start with http:// or https://")


class Recorded:
	name = "recorded"

	def __init__(self):
		self.values = []

	def check(self, value: str):
		self.values.append(value)


def test_reports_the_failing_rule_and_its_message():
	field = text_field("url", [WebURL()])

	failure = failure_of(field, Input({"url": "example.com"}))

	assert_eq(failure.rule, "web_url")
	assert_eq(failure.message, "must start with http:// or https://")


def test_stops_at_the_first_failing_rule():
	recorded = Recorded()
	field = text_field("url", [WebURL(), recorded])

	failure_of(field, Input({"url": "example.com"}))

	assert_eq(recorded.values, [])


def test_requires_fields_without_defaults_before_other_rules():
	recorded = Recorded()
	field = text_field("title", [recorded])

	failure = failure_of(field, Input())

	assert_eq(failure.rule, "required")
	assert_eq(failure.message, "must be provided")
	assert_eq(recorded.values, [])


def test_skips_rules_for_missing_optional_fields():
	recorded = Recorded()
	field = Field("url", parser.Str(), "", False, [WebURL(), recorded])

	assert_eq(field.validate(Input()), "")
	assert_eq(recorded.values, [])


def test_skips_rules_after_a_parse_error():
	recorded = Recorded()
	field = Field("board_ids", parser.List(parser.UUID()), [], False, [recorded])

	failure = failure_of(field, Input({"board_ids": ["not-a-uuid"]}))

	assert_eq(failure.rule, "invalid")
	assert_eq(failure.message, "must be a valid UUID")
	assert_eq(recorded.values, [])


def text_field(name, rules):
	return Field(name, parser.Str(), MISSING, False, rules)


def failure_of(field, input):
	with assert_raises(Failure) as raised:
		field.validate(input)

	return raised.exception
