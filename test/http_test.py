from luna.test.assertion import assert_eq, assert_that

from helios.http import Cookies, Headers, Input, Method, Request, URL


def test_encodes_url_path():
	url = URL("/about")

	assert_eq(str(url), "/about")


def test_encodes_url_query():
	url = URL("/search", {"q": "today", "tags": ["news", "politics"]})

	assert_eq(str(url), "/search?q=today&tags=news&tags=politics")


def test_gets_request_referrer():
	request = Request(
		Method.GET,
		URL("/boards/123456/edit"),
		Headers({"Referer": "/boards/"}),
		Input(),
	)

	assert_eq(request.referrer, "/boards/")


def test_doesnt_get_empty_referrer():
	request = Request(Method.GET, URL("/boards/example/edit"), Headers(), Input())

	assert_that(request.referrer is None)


def test_queries_headers_without_case():
	headers = Headers()
	headers["content-type"] = "text/html"

	assert_that("Content-Type" in headers)
	assert_eq(str(headers["Content-Type"]), "text/html")


def test_stores_multiple_headers():
	headers = Headers()

	headers["Accept"] = "text/html"
	headers["Accept"] += "text/plain"

	assert_eq(list(headers["Accept"]), ["text/html", "text/plain"])
	assert_eq(str(headers["Accept"]), "text/html, text/plain")


def test_iterates_header_pairs():
	headers = Headers()
	headers["Accept"] = "text/html"
	headers["User-Agent"] = "Mozilla/5.0"

	assert_eq(list(headers), [("Accept", "text/html"), ("User-Agent", "Mozilla/5.0")])


def test_encodes_cookies():
	cookies = Cookies()
	cookies["session_id"] = "51d0d53a-11dd-47a5-b438-5eb1b84e1432"
	cookies["session_id"].http_only = True

	assert_eq(
		str(cookies["session_id"]),
		"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/; HttpOnly",
	)


def test_adapts_cookies_from_headers():
	headers = Headers()
	headers["Cookie"] = (
		"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; csrf_token=fd3e6aff6360af4d6ba905d4299cff81"
	)

	cookies = Cookies.from_headers(headers)

	assert_eq(cookies["session_id"].val, "51d0d53a-11dd-47a5-b438-5eb1b84e1432")
	assert_eq(cookies["csrf_token"].val, "fd3e6aff6360af4d6ba905d4299cff81")


def test_adapts_cookies_to_headers():
	cookies = Cookies()
	cookies["session_id"] = "51d0d53a-11dd-47a5-b438-5eb1b84e1432"
	cookies["csrf_token"] = "fd3e6aff6360af4d6ba905d4299cff81"

	headers = cookies.to_headers()

	assert_eq(
		list(headers["Set-Cookie"]),
		[
			"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/",
			"csrf_token=fd3e6aff6360af4d6ba905d4299cff81; Path=/",
		],
	)
