from luna.test.assertion import assert_eq, assert_raises

from helios.declarative import MISSING
from helios.form import RuleError, parser
from helios.form.form import Failure, Field
from helios.form.rule import Required
from helios.http import Input


class Lowercase:
	name = "lowercase"
	message = "must be lowercase"

	def check(self, value: str) -> str:
		return value.lower()


class WebURL:
	name = "web_url"
	message = "must start with http:// or https://"

	def check(self, value: str) -> str:
		if not value.startswith(("http://", "https://")):
			raise RuleError()
		else:
			return value


class MaxLength:
	name = "max_length"

	def __init__(self, limit: int):
		self.limit = limit

	@property
	def message(self) -> str:
		return f"must be at most {self.limit} characters"

	def check(self, value: str) -> str:
		if len(value) > self.limit:
			raise RuleError()
		else:
			return value


class Available:
	name = "available"
	message = "must be available"

	def check(self, value: str) -> str:
		raise RuleError("must not be a reserved name")


class Recorded:
	name = "recorded"
	message = "never fails"

	def __init__(self):
		self.values = []

	def check(self, value: str) -> str:
		self.values.append(value)
		return value


def test_required_passes_present_values():
	assert_eq(Required().check("Intro"), "Intro")


def test_required_rejects_missing_values():
	with assert_raises(RuleError) as raised:
		Required().check(None)

	assert_eq(raised.exception.message, None)
	assert_eq((Required.name, Required.message), ("required", "must be provided"))


def test_runs_rules_in_order_on_parsed_values():
	field = text_field("url", [Lowercase(), WebURL()])

	assert_eq(
		field.validate(Input({"url": " HTTPS://Example.com "})), "https://example.com"
	)


def test_reports_the_failing_rule_and_its_message():
	field = text_field("url", [WebURL()])

	failure = failure_of(field, Input({"url": "example.com"}))

	assert_eq(failure.rule, "web_url")
	assert_eq(failure.message, "must start with http:// or https://")


def test_rules_with_parameters_supply_their_messages():
	field = text_field("title", [MaxLength(3)])

	failure = failure_of(field, Input({"title": "Hello"}))

	assert_eq(failure.rule, "max_length")
	assert_eq(failure.message, "must be at most 3 characters")


def test_rule_errors_can_replace_the_default_message():
	field = text_field("handle", [Available()])

	failure = failure_of(field, Input({"handle": "admin"}))

	assert_eq(failure.rule, "available")
	assert_eq(failure.message, "must not be a reserved name")


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
