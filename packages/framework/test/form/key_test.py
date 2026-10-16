from luna.test.assertion import assert_eq

from helios.form.key import Key


def test_parses_field_keys():
	assert_eq(Key.parse("tags"), Key("tags"))
	assert_eq(Key.parse("tags.length"), Key("tags", rest="length"))


def test_parses_item_keys():
	assert_eq(Key.parse("tags.*"), Key("tags", item=True))
	assert_eq(Key.parse("tags.*.length"), Key("tags", item=True, rest="length"))


def test_writes_keys_as_text():
	assert_eq(
		[
			str(Key("tags")),
			str(Key("tags", rest="required")),
			str(Key("tags", item=True)),
			str(Key("tags", item=True, rest="length")),
		],
		["tags", "tags.required", "tags.*", "tags.*.length"],
	)
