from uuid import uuid4

from luna.test.assertion import (
	assert_eq,
	assert_raises,
)

from helios.url import Pattern, URL


def test_parses_placeholder_followed_by_text():
	pattern = Pattern.parse("/posts/{slug}.xml")

	assert_eq(pattern.parameters["slug"].suffix, ".xml")


def test_parses_placeholder_with_converter_followed_by_text():
	pattern = Pattern.parse("/posts/{id:uuid}.xml")

	assert_eq(pattern.parameters["id"].suffix, ".xml")


def test_matches_url_with_text_after_value():
	pattern = Pattern.parse("/posts/{slug}.xml")
	slug = f"post-{uuid4().hex}"

	parameters = pattern.match(URL(f"/posts/{slug}.xml"))

	assert_eq(parameters, {"slug": slug})


def test_matches_converted_value_followed_by_text():
	pattern = Pattern.parse("/posts/{id:uuid}.xml")
	identifier = uuid4()

	parameters = pattern.match(URL(f"/posts/{identifier}.xml"))

	assert_eq(parameters, {"id": identifier})


def test_does_not_match_url_without_the_text():
	pattern = Pattern.parse("/posts/{slug}.xml")

	parameters = pattern.match(URL(f"/posts/{uuid4().hex}"))

	assert_eq(parameters, None)


def test_does_not_match_url_with_other_text():
	pattern = Pattern.parse("/posts/{slug}.xml")

	parameters = pattern.match(URL(f"/posts/{uuid4().hex}.json"))

	assert_eq(parameters, None)


def test_builds_path_with_text_after_value():
	pattern = Pattern.parse("/posts/{slug}.xml")
	slug = f"post-{uuid4().hex}"

	path = pattern.path({"slug": slug})

	assert_eq(path, f"/posts/{slug}.xml")


def test_builds_path_with_converted_value_followed_by_text():
	pattern = Pattern.parse("/posts/{id:uuid}.xml")
	identifier = uuid4()

	path = pattern.path({"id": identifier})

	assert_eq(path, f"/posts/{identifier}.xml")


def test_rejects_text_before_placeholder():
	with assert_raises(ValueError):
		Pattern.parse("/posts/draft-{slug}")


def test_rejects_two_placeholders_in_one_segment():
	with assert_raises(ValueError):
		Pattern.parse("/posts/{slug}.{format}")
