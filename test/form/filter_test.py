from luna.test.assertion import assert_eq

from helios.form.filter import Compact, Trim, Unspace, Upcase


def test_trim_removes_surrounding_whitespace():
	assert_eq(Trim().apply("\t Intro  \n"), "Intro")
	assert_eq(Trim().apply("Read  later"), "Read  later")


def test_upcase_uppercases_letters():
	assert_eq(Upcase().apply("abcd-efgh 12"), "ABCD-EFGH 12")


def test_unspace_removes_all_whitespace():
	assert_eq(Unspace().apply("ABCD EFGH"), "ABCDEFGH")
	assert_eq(Unspace().apply(" \tABCD\nEFGH "), "ABCDEFGH")
	assert_eq(Unspace().apply("ABCD EFGH JKLM"), "ABCDEFGHJKLM")


def test_compact_drops_blank_items_and_keeps_order():
	assert_eq(
		Compact().apply(["design", "", "reading", "  ", "art"]),
		["design", "reading", "art"],
	)


def test_compact_keeps_padding_on_items_it_keeps():
	assert_eq(Compact().apply([" design ", "\t"]), [" design "])


def test_compares_and_shows_filters_by_value():
	assert_eq(Trim(), Trim())
	assert_eq(repr(Upcase()), "Upcase()")
