from luna.test.assertion import assert_eq
from markupsafe import Markup

from helios.view import Attributes


def test_converts_python_names_to_html_names():
	attributes = Attributes(class_="card", data_turbo_frame="modal")

	html = str(attributes)

	assert_eq(attributes.names(), {"class", "data-turbo-frame"})
	assert_eq(html, 'class="card" data-turbo-frame="modal"')


def test_drops_leading_underscores_from_names():
	attributes = Attributes(_private=True)

	html = str(attributes)

	assert_eq(html, "private")


def test_renders_true_as_bare_name():
	attributes = Attributes(hidden=True)

	html = str(attributes)

	assert_eq(html, "hidden")


def test_omits_false_and_none():
	attributes = Attributes(id="menu", hidden=False, data_state=None)

	html = str(attributes)

	assert_eq(html, 'id="menu"')


def test_escapes_values():
	attributes = Attributes(data_label='"><script>', data_count=3)

	html = str(attributes)

	assert_eq(html, 'data-label="&#34;&gt;&lt;script&gt;" data-count="3"')


def test_renders_as_markup():
	attributes = Attributes(id="menu")

	html = attributes.__html__()

	assert isinstance(html, Markup)
	assert_eq(html, 'id="menu"')


def test_drops_falsy_classes_from_lists():
	attributes = Attributes(class_=["link", False, None, "", "link--active"])

	html = str(attributes)

	assert_eq(html, 'class="link link--active"')


def test_omits_falsy_classes():
	attributes = Attributes(class_=False, id="menu")

	html = str(attributes)

	assert_eq(html, 'id="menu"')


def test_omits_empty_class_lists():
	attributes = Attributes(class_=[False], id="menu")

	html = str(attributes)

	assert_eq(html, 'id="menu"')


def test_merges_classes_after_defaults_without_duplicates():
	attributes = Attributes(class_=["pin-link", "external-link"])

	merged = attributes.merge(class_="external-link link")

	assert_eq(str(merged), 'class="external-link link pin-link"')


def test_merges_default_class_lists():
	attributes = Attributes(class_="pin-link")

	merged = attributes.merge(class_=["external-link", False])

	assert_eq(str(merged), 'class="external-link pin-link"')


def test_prefers_caller_values_over_defaults():
	attributes = Attributes(target="_self", hidden=False)

	merged = attributes.merge(target="_blank", hidden=True, rel="noopener")

	assert_eq(str(merged), 'target="_self" rel="noopener"')


def test_orders_defaults_before_caller_attributes():
	attributes = Attributes(id="link", class_="pin-link")

	merged = attributes.merge(class_="external-link", data_turbo=False)

	assert_eq(str(merged), 'class="external-link pin-link" id="link"')


def test_merge_leaves_original_unchanged():
	attributes = Attributes(class_="pin-link")

	attributes.merge(class_="external-link", id="link")

	assert_eq(str(attributes), 'class="pin-link"')


def test_builds_from_html_names():
	attributes = Attributes.from_html_names(
		{"data-turbo-frame": "modal", "class": "a b"}
	)

	html = str(attributes)

	assert_eq(html, 'data-turbo-frame="modal" class="a b"')


def test_renders_empty_bag_as_empty_string():
	attributes = Attributes()

	html = str(attributes)

	assert_eq(attributes.names(), set())
	assert_eq(html, "")
