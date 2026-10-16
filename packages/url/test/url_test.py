from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_not_in,
	assert_raises,
)

from helios.url import Query, URL


def test_encodes_url_path():
	url = URL("/about")

	assert_eq(str(url), "/about")


def test_encodes_url_query():
	url = URL("/search", Query({"q": "today", "tags": ["news", "politics"]}))

	assert_eq(str(url), "/search?q=today&tags=news&tags=politics")


def test_encodes_absolute_url():
	url = URL("/search", Query({"q": "today"}), scheme="https", host="example.com")

	assert_eq(str(url), "https://example.com/search?q=today")


def test_parses_absolute_url_components():
	url = URL.parse("https://reader:secret@example.com:8443/search?q=today#results")

	assert_eq(url.scheme, "https")
	assert_eq(url.user, "reader")
	assert_eq(url.password, "secret")
	assert_eq(url.host, "example.com")
	assert_eq(url.port, 8443)
	assert_eq(url.path, "/search")
	assert_eq(url.query.first("q"), "today")
	assert_eq(url.fragment, "results")


def test_round_trips_parsed_urls():
	raws = [
		"https://example.com:8443/search",
		"https://reader:p%40ss@example.com/",
		"https://reader@Example.com/",
		"http://[::1]:8000/posts/",
		"https://example.com/posts/intro/#comments",
		"https://example.com/search?flag&q=a+b%20c&q=%2F",
		"/posts/?sort=recent#top",
		"/redirect?to=https://example.com/",
	]

	for raw in raws:
		assert_eq(str(URL.parse(raw)), raw)


def test_parses_relative_url_query():
	url = URL.parse("/search?q=today")

	assert_eq(url.host, None)
	assert_eq(url.path, "/search")
	assert_eq(url.query.first("q"), "today")


def test_parses_absolute_url_query():
	url = URL.parse(
		"https://example.com/search?q=today&tags=news&tags=politics&page=&flag"
	)

	assert_eq(url.query.first("q"), "today")
	assert_eq(url.query.all("q"), ["today"])
	assert_eq(url.query.all("tags"), ["news", "politics"])
	assert_eq(url.query.first("page"), "")
	assert_eq(url.query.first("flag"), "")


def test_rejects_malformed_urls():
	raws = [
		"example.com",
		"example.com:8443",
		"mailto:reader@example.com",
		"//example.com/posts/",
		"https:///posts/",
		"https://exa mple.com/",
		"https://example.com:invalid/",
		"http://[::1/",
	]

	for raw in raws:
		with assert_raises(ValueError):
			URL.parse(raw)


def test_rejects_inconsistent_url_components():
	with assert_raises(ValueError):
		URL("/", scheme="https")
	with assert_raises(ValueError):
		URL("/", port=8443)
	with assert_raises(ValueError):
		URL("/", user="reader")
	with assert_raises(ValueError):
		URL("/", scheme="https", host="example.com", password="secret")
	with assert_raises(ValueError):
		URL("posts/")


def test_reads_single_and_repeated_query_values():
	query = Query({"q": "today", "tags": ["news", "politics"]})

	assert_in("q", query)
	assert_eq(query.first("q"), "today")
	assert_eq(query.all("q"), ["today"])
	assert_eq(query.first("tags"), "news")
	assert_eq(query.all("tags"), ["news", "politics"])


def test_reads_missing_query_values_as_empty():
	query = Query({"tags": []})

	assert_not_in("q", query)
	assert_eq(query.first("q"), None)
	assert_eq(query.all("q"), [])
	assert_eq(query.first("tags"), None)
	assert_eq(query.all("tags"), [])


def test_changing_read_query_values_leaves_query_unchanged():
	tags = ["news"]
	query = Query({"tags": tags})

	tags.append("politics")
	query.all("tags").append("sport")

	assert_eq(query.all("tags"), ["news"])
