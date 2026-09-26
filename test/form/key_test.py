from luna.test.assertion import assert_eq

from helios.form.key import Key


def test_parses_field_keys():
	assert_eq(Key.parse("tags"), Key("tags"))
	assert_eq(Key.parse("tags.length"), Key("tags", False, "length"))


def test_parses_item_keys():
	assert_eq(Key.parse("tags.*"), Key("tags", True))
	assert_eq(Key.parse("tags.*.length"), Key("tags", True, "length"))


def test_writes_keys_as_text():
	assert_eq(
		[
			str(Key("tags")),
			str(Key("tags", False, "required")),
			str(Key("tags", True)),
			str(Key("tags", True, "length")),
		],
		["tags", "tags.required", "tags.*", "tags.*.length"],
	)
