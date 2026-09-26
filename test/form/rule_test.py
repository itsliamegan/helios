from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises

from helios.form import Distinct, Length, Only, RuleError


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
