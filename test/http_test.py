from typing import cast

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.http import (
	Buffered,
	Cookie,
	Cookies,
	File,
	Files,
	Headers,
	Input,
	Method,
	Query,
	Request,
	Response,
	SameSite,
	URL,
)


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

	assert_that(url.host is None)
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

	assert_that("q" in query)
	assert_eq(query.first("q"), "today")
	assert_eq(query.all("q"), ["today"])
	assert_eq(query.first("tags"), "news")
	assert_eq(query.all("tags"), ["news", "politics"])


def test_reads_missing_query_values_as_empty():
	query = Query({"tags": []})

	assert_that("q" not in query)
	assert_that(query.first("q") is None)
	assert_eq(query.all("q"), [])
	assert_that(query.first("tags") is None)
	assert_eq(query.all("tags"), [])


def test_changing_read_query_values_leaves_query_unchanged():
	tags = ["news"]
	query = Query({"tags": tags})

	tags.append("politics")
	query.all("tags").append("sport")

	assert_eq(query.all("tags"), ["news"])


def test_encodes_text_and_binary_bodies():
	assert_eq(Buffered("Hello, world!").to_bytes(), b"Hello, world!")
	assert_eq(Buffered(b"\x00\xff").to_bytes(), b"\x00\xff")


def test_creates_file_response():
	response = Response.file(b"\x00\xff", "report.pdf", "application/pdf")

	assert isinstance(response.body, Buffered)
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
		URL("/posts/123456/edit"),
		Headers({"Referer": "/posts/"}),
	)

	assert_eq(request.referrer, "/posts/")


def test_doesnt_get_empty_referrer():
	request = Request(Method.GET, URL("/posts/example/edit"))

	assert_that(request.referrer is None)


def test_queries_headers_without_case():
	headers = Headers()
	headers["content-type"] = "text/html"

	assert_that("Content-Type" in headers)
	assert_eq(str(headers["Content-Type"]), "text/html")


def test_preserves_header_name_spelling():
	headers = Headers({"ETag": '"abc123"'})

	assert_eq(list(headers), [("ETag", '"abc123"')])
	assert_eq(str(headers["etag"]), '"abc123"')


def test_rejects_newlines_in_header_values():
	with assert_raises(ValueError):
		Headers({"X-Message": "hello\r\nX-Injected: true"})

	headers = Headers({"X-Message": "hello"})
	with assert_raises(ValueError):
		headers["X-Message"] = "hello\nworld"
	with assert_raises(ValueError):
		headers["X-Message"] += "hello\rworld"

	assert_eq(list(headers["X-Message"]), ["hello"])


def test_stores_multiple_headers():
	headers = Headers()

	headers["Accept"] = "text/html"
	headers["Accept"] += "text/plain"

	assert_eq(list(headers["Accept"]), ["text/html", "text/plain"])
	assert_eq(str(headers["Accept"]), "text/html, text/plain")


def test_updates_header_through_reference():
	headers = Headers({"Accept": "text/html"})
	header = headers["Accept"]

	header += "text/plain"

	assert_that(header is headers["Accept"])
	assert_eq(list(headers["Accept"]), ["text/html", "text/plain"])


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

	assert_eq(cookies["session_id"].value, "51d0d53a-11dd-47a5-b438-5eb1b84e1432")
	assert_eq(cookies["csrf_token"].value, "fd3e6aff6360af4d6ba905d4299cff81")
	assert_eq(cookies["message"].value, "hello world")


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


def test_assigns_cookie_object():
	cookies = Cookies()
	cookie = Cookie("session_id", "abc", http_only=True)

	cookies["session_id"] = cookie

	assert_that(cookies["session_id"] is cookie)


def test_stores_uploaded_files():
	avatar = File(b"image bytes", "avatar.png", "image/png")
	attachments = [
		File(b"first", "first.txt", "text/plain"),
		File(b"second", "second.txt", "text/plain"),
	]
	files = Files({"avatar": avatar, "attachments": attachments})

	assert_that("avatar" in files)
	assert_that(files.first("avatar") is avatar)
	assert_eq(files.all("avatar"), [avatar])
	assert_that(files.first("attachments") is attachments[0])
	assert_eq(files.all("attachments"), attachments)


def test_reads_missing_files_as_empty():
	files = Files()

	assert_that("avatar" not in files)
	assert_that(files.first("avatar") is None)
	assert_eq(files.all("avatar"), [])


def test_reads_single_and_repeated_input():
	input = Input({"title": "Intro", "tags": ["art", "news"]})

	assert_that("title" in input)
	assert_eq(input.first("title"), "Intro")
	assert_eq(input.all("title"), ["Intro"])
	assert_eq(input.first("tags"), "art")
	assert_eq(input.all("tags"), ["art", "news"])


def test_reads_missing_input_as_empty():
	input = Input({"tags": []})

	assert_that("title" not in input)
	assert_that(input.first("title") is None)
	assert_eq(input.all("title"), [])
	assert_that(input.first("tags") is None)
	assert_eq(input.all("tags"), [])


def test_changing_read_input_values_leaves_input_unchanged():
	tags = ["art"]
	input = Input({"tags": tags})

	tags.append("news")
	input.all("tags").append("travel")

	assert_eq(input.all("tags"), ["art"])


def test_removes_input():
	input = Input({"_method": "delete", "title": "Intro"})

	del input["_method"]

	assert_that("_method" not in input)
	assert_eq(input.first("title"), "Intro")
