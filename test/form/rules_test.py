from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.form import FormError, Rule, RuleError, Rules, parser
from helios.form.field import Field
from helios.form.key import Key
from helios.form.rule import Length


class Reserved(Rule[str]):
	name = "reserved"

	def check(self, value: str):
		if value == "admin":
			raise RuleError("must not be a reserved name")


class Taken(Rule[str]):
	name = "taken"

	def check(self, value: str):
		if value == "admin":
			raise RuleError("must not be taken")


class Recorded(Rule[object]):
	name = "recorded"

	def __init__(self):
		self.values = []

	def check(self, value: object):
		self.values.append(value)


def test_passes_values_that_meet_every_rule():
	field = Field("tags", parser.List(parser.Str()), [])
	rules = Rules({"tags.*": [Length(maximum=5)], "tags": [Length(maximum=2)]})

	rules.check(field, ["art", "news"])


def test_keys_failures_by_field_and_rule_name():
	field = Field("handle", parser.Str())
	rules = Rules({"handle": [Reserved()]})

	error = rule_error_of(rules, field, "admin")

	assert_eq(error.key, Key("handle", rest="reserved"))
	assert_eq(error.message, "must not be a reserved name")


def test_runs_rules_in_declared_order():
	field = Field("handle", parser.Str())
	rules = Rules({"handle": [Reserved(), Taken()]})

	error = rule_error_of(rules, field, "admin")

	assert_eq(error.key, Key("handle", rest="reserved"))


def test_stops_at_the_first_failing_rule():
	recorded = Recorded()
	field = Field("handle", parser.Str())
	rules = Rules({"handle": [Reserved(), recorded]})

	rule_error_of(rules, field, "admin")

	assert_eq(recorded.values, [])


def test_runs_item_rules_before_field_rules():
	field = Field("tags", parser.List(parser.Str()), [])
	rules = Rules({"tags.*": [Length(maximum=3)], "tags": [Length(maximum=1)]})

	error = rule_error_of(rules, field, ["a", "long"])

	assert_eq(error.key, Key("tags", item=True, rest="length"))
	assert_eq(error.message, "must be at most 3 characters")


def test_keys_field_rule_failures_on_lists_as_field_failures():
	field = Field("tags", parser.List(parser.Str()), [])
	rules = Rules({"tags": [Length(maximum=1)]})

	error = rule_error_of(rules, field, ["a", "b"])

	assert_eq(error.key, Key("tags", rest="length"))
	assert_that(not error.key.item)


def test_stops_at_the_first_failing_item():
	recorded = Recorded()
	field = Field("tags", parser.List(parser.Str()), [])
	rules = Rules({"tags.*": [recorded, Reserved()]})

	rule_error_of(rules, field, ["design", "admin", "art"])

	assert_eq(recorded.values, ["design", "admin"])


def test_rejects_keys_with_anything_after_the_field_or_items():
	with assert_raises(FormError) as raised:
		Rules({"tags.*.name": [Length(maximum=5)]})

	assert_eq(
		str(raised.exception),
		"Rules has 'tags.*.name', which is neither 'tags' nor 'tags.*'",
	)


def rule_error_of(rules, field, value):
	with assert_raises(RuleError) as raised:
		rules.check(field, value)

	return raised.exception
