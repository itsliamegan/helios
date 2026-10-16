from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_is,
	assert_is_instance,
	assert_is_not,
	assert_not,
	assert_not_eq,
	assert_not_in,
	assert_not_none,
	assert_raises,
	assert_that,
)


def test_truthiness_assertions():
	assert_that(1)
	assert_not(0)

	assert str(raised_by(lambda: assert_that(0))) == "expected: truthy\nactual:   0"
	assert str(raised_by(lambda: assert_not(1))) == "expected: falsy\nactual:   1"


def test_equality_assertions():
	assert_eq({"name": "Alice"}, {"name": "Alice"})
	assert_not_eq("Alice", "Bob")

	assert (
		str(raised_by(lambda: assert_eq("Alice", "Bob")))
		== "expected: 'Bob'\nactual:   'Alice'"
	)
	assert str(raised_by(lambda: assert_not_eq("Bob", "Bob"))) == (
		"expected: different\nactual:   'Bob'"
	)


def test_equality_assertions_diff_multiline_values():
	assert str(raised_by(lambda: assert_eq("Alice\nBob\n", "Alice\nCarol\n"))) == (
		"expected: -, actual: +\n  Alice\n- Carol\n+ Bob"
	)

	people = [
		{"name": "Alice", "email": "alice@example.com"},
		{"name": "Bob", "email": "bob@example.com"},
	]
	expected = [
		{"name": "Alice", "email": "alice@example.com"},
		{"name": "Bob", "email": "bob@example.org"},
	]
	assert str(raised_by(lambda: assert_eq(people, expected))) == (
		"expected: -, actual: +\n"
		"  [{'name': 'Alice', 'email': 'alice@example.com'},\n"
		"-  {'name': 'Bob', 'email': 'bob@example.org'}]\n"
		"?                                         ^^\n"
		"+  {'name': 'Bob', 'email': 'bob@example.com'}]\n"
		"?                                        + ^"
	)


def test_membership_assertions():
	assert_in("Alice", ["Alice", "Bob"])
	assert_not_in("Carol", ["Alice", "Bob"])

	assert str(raised_by(lambda: assert_in("Carol", ["Alice", "Bob"]))) == (
		"expected: contains 'Carol'\nactual:   ['Alice', 'Bob']"
	)
	assert str(raised_by(lambda: assert_not_in("Bob", ["Alice", "Bob"]))) == (
		"expected: excludes 'Bob'\nactual:   ['Alice', 'Bob']"
	)


def test_identity_assertions():
	names = ["Alice"]
	assert_is(names, names)
	assert_is_not(names, ["Alice"])

	assert str(raised_by(lambda: assert_is(names, ["Alice"]))) == (
		"expected: same object as ['Alice']\nactual:   ['Alice']"
	)
	assert str(raised_by(lambda: assert_is_not(names, names))) == (
		"expected: different object\nactual:   ['Alice']"
	)


def test_narrowing_assertions():
	name: str | None = "Alice"
	value: object = 1
	assert assert_not_none(name).upper() == "ALICE"
	assert assert_is_instance(value, int) + 1 == 2

	assert str(raised_by(lambda: assert_not_none(None))) == (
		"expected: not None\nactual:   None"
	)
	assert str(raised_by(lambda: assert_is_instance("Alice", int))) == (
		"expected: instance of int\nactual:   'Alice'"
	)


def test_custom_messages():
	assert str(raised_by(lambda: assert_that(False, "not true"))) == "not true"
	assert str(raised_by(lambda: assert_eq(1, 2, "not equal"))) == "not equal"


def test_assert_raises():
	with assert_raises(ValueError):
		int("not an integer")


def test_assert_raises_exposes_exception():
	with assert_raises(ValueError) as raised:
		int("not an integer")

	assert isinstance(raised.exception, ValueError)
	assert "not an integer" in str(raised.exception)


def test_assert_raises_refuses_exception_before_one_is_raised():
	with assert_raises(ValueError) as raised:
		assert str(raised_by(lambda: raised.exception)) == "no exception captured"
		int("not an integer")


def test_assert_raises_fails_when_nothing_is_raised():
	def raise_nothing():
		with assert_raises(ValueError):
			pass

	assert str(raised_by(raise_nothing)) == "expected: raise ValueError"


def test_assert_raises_does_not_hide_unexpected_exceptions():
	try:
		with assert_raises(TypeError):
			raise ValueError("unexpected")
	except ValueError as err:
		assert str(err) == "unexpected"
	else:
		raise AssertionError("Expected the unexpected exception to propagate")


def raised_by(fn):
	try:
		fn()
	except AssertionError as err:
		return err
	raise AssertionError("Expected an AssertionError")
