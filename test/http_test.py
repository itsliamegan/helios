from typing import cast

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.http import (
	Body,
	Cookie,
	Cookies,
	File,
	Files,
	Headers,
	Input,
	Method,
	Request,
	Response,
	SameSite,
	URL,
)


def test_encodes_url_path():
	url = URL("/about")

	assert_eq(str(url), "/about")


def test_encodes_url_query():
	url = URL("/search", {"q": "today", "tags": ["news", "politics"]})

	assert_eq(str(url), "/search?q=today&tags=news&tags=politics")


def test_encodes_absolute_url():
	url = URL("/search", {"q": "today"}, scheme="https", host="example.com")

	assert_eq(str(url), "https://example.com/search?q=today")


def test_preserves_absolute_url_port():
	url = URL("https://example.com:8443/search")

	assert_eq(url.scheme, "https")
	assert_eq(url.host, "example.com")
	assert_eq(url.port, 8443)
	assert_eq(str(url), "https://example.com:8443/search")


def test_encodes_text_and_binary_bodies():
	assert_eq(Body("Hello, world!").to_bytes(), b"Hello, world!")
	assert_eq(Body(b"\x00\xff").to_bytes(), b"\x00\xff")


def test_creates_file_response():
	response = Response.file(b"\x00\xff", "report.pdf", "application/pdf")

	assert_eq(response.body.to_bytes(), b"\x00\xff")
	assert_eq(str(response.headers["Content-Type"]), "application/pdf")
	assert_eq(
		str(response.headers["Content-Disposition"]),
		'attachment; filename="report.pdf"',
	)
	assert_eq(str(response.headers["Content-Length"]), "2")


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
		"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; HttpOnly; Path=/",
	)


def test_encodes_secure_same_site_cookie():
	cookie = Cookie(
		"session_id",
		"51d0d53a-11dd-47a5-b438-5eb1b84e1432",
		http_only=True,
		secure=True,
		same_site="Lax",
	)

	assert_eq(
		str(cookie),
		"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Secure; HttpOnly; Path=/; SameSite=Lax",
	)


def test_encodes_unsafe_cookie_value():
	cookie = Cookie("message", "hello world")

	assert_eq(str(cookie), 'message="hello world"; Path=/')


def test_accepts_canonical_same_site_values():
	assert_that("SameSite=Lax" in str(Cookie("id", "1", same_site="Lax")))
	assert_that("SameSite=Strict" in str(Cookie("id", "1", same_site="Strict")))
	assert_that("SameSite=None" in str(Cookie("id", "1", same_site="None")))


def test_rejects_noncanonical_same_site_values():
	with assert_raises(ValueError):
		Cookie("id", "1", same_site=cast(SameSite, "lax"))

	cookie = Cookie("id", "1")
	with assert_raises(ValueError):
		cookie.same_site = cast(SameSite, "invalid")


def test_adapts_cookies_from_headers():
	headers = Headers()
	headers["Cookie"] = (
		"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432;"
		'csrf_token=fd3e6aff6360af4d6ba905d4299cff81;message="hello world"'
	)

	cookies = Cookies.from_headers(headers)

	assert_eq(cookies["session_id"].val, "51d0d53a-11dd-47a5-b438-5eb1b84e1432")
	assert_eq(cookies["csrf_token"].val, "fd3e6aff6360af4d6ba905d4299cff81")
	assert_eq(cookies["message"].val, "hello world")


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


def test_stores_uploaded_files():
	avatar = File(b"image bytes", "avatar.png", "image/png")
	attachments = [
		File(b"first", "first.txt", "text/plain"),
		File(b"second", "second.txt", "text/plain"),
	]
	files = Files({"avatar": avatar, "attachments": attachments})

	assert_that("avatar" in files)
	assert_that(files["avatar"] is avatar)
	assert_eq(files["attachments"], attachments)
