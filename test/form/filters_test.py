from luna.test.assertion import assert_eq, assert_raises

from helios.form import Filter, Filters, FormError, parser
from helios.form.field import Field
from helios.form.filter import Compact, Upcase


class Suffix(Filter[str]):
	def __init__(self, text: str):
		self.text = text

	def apply(self, value: str) -> str:
		return value + self.text


def test_trims_strings_by_default():
	field = Field("title", parser.Str(), trimmed=True)

	assert_eq(Filters().apply(field, "  Intro \n"), "Intro")


def test_keeps_padding_on_untrimmed_fields():
	field = Field("note", parser.Str(), "", trimmed=False)

	assert_eq(Filters().apply(field, "  - item\n"), "  - item\n")


def test_trims_list_items_and_keeps_blank_ones():
	field = Field("tags", parser.List(parser.Str()), [], trimmed=True)

	assert_eq(Filters().apply(field, [" a ", ""]), ["a", ""])


def test_applies_filters_in_declared_order():
	field = Field("code", parser.Str(), trimmed=True)
	filters = Filters({"code": [Suffix("a"), Upcase(), Suffix("b")]})

	assert_eq(filters.apply(field, " x "), "XAb")


def test_trims_before_declared_filters():
	field = Field("code", parser.Str(), trimmed=True)
	filters = Filters({"code": [Suffix("!")]})

	assert_eq(filters.apply(field, " x "), "x!")


def test_applies_item_filters_before_field_filters():
	field = Field("tags", parser.List(parser.Str()), [], trimmed=True)
	filters = Filters({"tags.*": [Suffix("!")], "tags": [Compact()]})

	assert_eq(filters.apply(field, ["a", " "]), ["a!", "!"])


def test_rejects_keys_with_anything_after_the_field_or_items():
	with assert_raises(FormError) as raised:
		Filters({"tags.*.name": [Upcase()]})
	with assert_raises(FormError):
		Filters({"tags.first": [Upcase()]})

	assert_eq(
		str(raised.exception),
		"Filters has 'tags.*.name', which is neither 'tags' nor 'tags.*'",
	)
