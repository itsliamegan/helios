from typing import cast

from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_is,
	assert_is_instance,
	assert_not_in,
	assert_raises,
)

from helios.http import (
	Buffered,
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
	Status,
	Stream,
	URL,
	sse,
)
from helios.http.error import NotFoundError


def test_encodes_text_and_binary_bodies():
	assert_eq(Buffered("Hello, world!").to_bytes(), b"Hello, world!")
	assert_eq(Buffered(b"\x00\xff").to_bytes(), b"\x00\xff")


def test_creates_file_response():
	response = Response.file(b"\x00\xff", "report.pdf", "application/pdf")

	body = assert_is_instance(response.body, Buffered)
	assert_eq(body.to_bytes(), b"\x00\xff")
	assert_eq(str(response.headers["Content-Type"]), "application/pdf")
	assert_eq(
		str(response.headers["Content-Disposition"]),
		'attachment; filename="report.pdf"',
	)
	assert_eq(str(response.headers["Content-Length"]), "2")


def test_creates_error_response():
	response = Response.error(NotFoundError())

	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(str(response.body), "404 Not Found")


def test_creates_event_stream_response():
	response = Response.event_stream(
		[
			sse.Event("New post", event="post", id="1"),
			sse.Comment("heartbeat"),
			sse.Event("New comment", event="comment", id="2"),
		]
	)

	body = assert_is_instance(response.body, Stream)
	assert_eq(response.status, Status.OK)
	assert_eq(str(response.headers["Content-Type"]), "text/event-stream; charset=utf-8")
	assert_eq(str(response.headers["Cache-Control"]), "no-cache")
	assert_eq(
		list(body.chunks),
		[
			b"event: post\ndata: New post\nid: 1\n\n",
			b": heartbeat\n\n",
			b"event: comment\ndata: New comment\nid: 2\n\n",
		],
	)


def test_gets_request_referrer():
	request = Request(
		Method.GET,
		URL("/posts/123456/edit"),
		Headers({"Referer": "/posts/"}),
	)

	assert_eq(request.referrer, "/posts/")


def test_doesnt_get_empty_referrer():
	request = Request(Method.GET, URL("/posts/example/edit"))

	assert_eq(request.referrer, None)


def test_queries_headers_without_case():
	headers = Headers()
	headers["content-type"] = "text/html"

	assert_in("Content-Type", headers)
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

	assert_is(header, headers["Accept"])
	assert_eq(list(headers["Accept"]), ["text/html", "text/plain"])


def test_adding_to_a_header_leaves_given_values_unchanged():
	given = ["text/html"]
	headers = Headers({"Accept": given})

	headers["Accept"] += "text/plain"

	assert_eq(given, ["text/html"])


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
	assert_in("SameSite=Lax", str(Cookie("id", "1", same_site="Lax")))
	assert_in("SameSite=Strict", str(Cookie("id", "1", same_site="Strict")))
	assert_in("SameSite=None", str(Cookie("id", "1", same_site="None")))


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

	assert_is(cookies["session_id"], cookie)


def test_stores_uploaded_files():
	avatar = File(b"image bytes", "avatar.png", "image/png")
	attachments = [
		File(b"first", "first.txt", "text/plain"),
		File(b"second", "second.txt", "text/plain"),
	]
	files = Files({"avatar": avatar, "attachments": attachments})

	assert_in("avatar", files)
	assert_is(files.first("avatar"), avatar)
	assert_eq(files.all("avatar"), [avatar])
	assert_is(files.first("attachments"), attachments[0])
	assert_eq(files.all("attachments"), attachments)


def test_reads_missing_files_as_empty():
	files = Files()

	assert_not_in("avatar", files)
	assert_eq(files.first("avatar"), None)
	assert_eq(files.all("avatar"), [])


def test_reads_single_and_repeated_input():
	input = Input({"title": "Intro", "tags": ["art", "news"]})

	assert_in("title", input)
	assert_eq(input.first("title"), "Intro")
	assert_eq(input.all("title"), ["Intro"])
	assert_eq(input.first("tags"), "art")
	assert_eq(input.all("tags"), ["art", "news"])


def test_reads_missing_input_as_empty():
	input = Input({"tags": []})

	assert_not_in("title", input)
	assert_eq(input.first("title"), None)
	assert_eq(input.all("title"), [])
	assert_eq(input.first("tags"), None)
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

	assert_not_in("_method", input)
	assert_eq(input.first("title"), "Intro")
