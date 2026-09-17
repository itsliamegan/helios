from io import BytesIO

from luna.test.assertion import assert_eq, assert_that
from werkzeug.test import EnvironBuilder

import helios.app
from helios.http import Body, Cookies, Headers, Method, Response, Status, URL
from helios.routing import Pattern, Route, Router
from helios.wsgi import Application, TestClient, adapt_env, adapt_res


def test_adapts_method():
	env = EnvironBuilder(method="GET").get_environ()

	req = adapt_env(env)

	assert_that(req.method is Method.GET)


def test_adapts_url():
	env = EnvironBuilder(path="/search?q=Intro").get_environ()

	req = adapt_env(env)

	assert_eq(req.url.path, "/search")
	assert_eq(req.url.query, {"q": "Intro"})


def test_adapts_headers():
	env = EnvironBuilder(
		headers=[("Accept", "text/html"), ("User-Agent", "Mozilla/5.0")]
	).get_environ()

	req = adapt_env(env)

	assert_eq(str(req.headers["Accept"]), "text/html")
	assert_eq(str(req.headers["User-Agent"]), "Mozilla/5.0")


def test_adapts_content_info():
	env = EnvironBuilder(content_type="text/html", content_length="100").get_environ()

	req = adapt_env(env)

	assert_eq(str(req.headers["Content-Type"]), "text/html")
	assert_eq(str(req.headers["Content-Length"]), "100")


def test_adapts_form_input():
	env = EnvironBuilder(data={"content": "An interesting article."}).get_environ()

	req = adapt_env(env)

	assert_eq(req.input["content"], "An interesting article.")


def test_adapts_multipart_input_and_files():
	env = EnvironBuilder(
		data={
			"title": "Summer",
			"photo": (BytesIO(b"image bytes"), "beach.jpg", "image/jpeg"),
		}
	).get_environ()

	req = adapt_env(env)

	assert_eq(req.input["title"], "Summer")
	photo = req.files["photo"]
	assert_eq(photo.content, b"image bytes")
	assert_eq(photo.filename, "beach.jpg")
	assert_eq(photo.content_type, "image/jpeg")


def test_adapts_repeated_multipart_input_and_files():
	env = EnvironBuilder(
		data={
			"tag": ["summer", "holiday"],
			"photo": [
				(BytesIO(b"first"), "first.jpg"),
				(BytesIO(b"second"), "second.jpg"),
			],
		}
	).get_environ()

	req = adapt_env(env)

	assert_eq(req.input["tag"], ["summer", "holiday"])
	photos = req.files["photo"]
	assert_eq([photo.content for photo in photos], [b"first", b"second"])
	assert_eq([photo.filename for photo in photos], ["first.jpg", "second.jpg"])


def test_adapts_res():
	res = Response(
		Status.OK,
		Headers({"Content-Type": "text/html"}),
		Cookies({"session_id": "51d0d53a-11dd-47a5-b438-5eb1b84e1432"}),
		Body("<h1>Index</h1>"),
	)

	def start_res(status, pairs):
		assert_eq(status, "200 OK")
		assert_eq(
			pairs,
			[
				("Content-Type", "text/html"),
				(
					"Set-Cookie",
					"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/",
				),
			],
		)

	body = adapt_res(res, start_res)

	assert_eq(list(body), [b"<h1>Index</h1>"])


def test_adapts_binary_res():
	res = Response.file(b"\x00\xff", "data.bin", "application/octet-stream")

	def start_res(status, pairs):
		assert_eq(status, "200 OK")

	body = adapt_res(res, start_res)

	assert_eq(list(body), [b"\x00\xff"])


def test_adapts_multiple_cookies():
	res = Response.empty()
	res.cookies["session_id"] = "51d0d53a-11dd-47a5-b438-5eb1b84e1432"
	res.cookies["csrf_token"] = "fd3e6aff6360af4d6ba905d4299cff81"

	def start_res(status, pairs):
		assert_eq(
			pairs,
			[
				(
					"Set-Cookie",
					"session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/",
				),
				("Set-Cookie", "csrf_token=fd3e6aff6360af4d6ba905d4299cff81; Path=/"),
			],
		)

	adapt_res(res, start_res)


def test_client_routes_get_and_exposes_response():
	def show(req, ctx):
		res = Response.html("<h1>Index</h1>")
		res.headers["X-Result"] = "found"
		return res

	client = make_client([Route(Method.GET, Pattern("/"), show)])

	res = client.get("/")

	assert_eq(res.status_code, 200)
	assert_eq(res.headers["Content-Type"], "text/html")
	assert_eq(res.headers["X-Result"], "found")
	assert_eq(res.text, "<h1>Index</h1>")


def test_client_sends_query_and_headers():
	def search(req, ctx):
		return Response.text(f"{req.url.query["q"]}|{req.headers["X-Filter"]}")

	client = make_client([Route(Method.GET, Pattern("/search"), search)])

	res = client.get(
		"/search",
		query={"q": "Intro"},
		headers={"X-Filter": "recent"},
	)

	assert_eq(res.text, "Intro|recent")


def test_client_sends_scalar_and_repeated_form_values():
	def create(req, ctx):
		board_ids = req.input["board_id"]
		return Response.text(f"{req.input["title"]}|{",".join(board_ids)}")

	client = make_client([Route(Method.POST, Pattern("/pins"), create)])
	form = {
		"title": "Reading",
		"board_id": ["first", "second"],
	}

	res = client.post("/pins", form=form)

	assert_eq(res.text, "Reading|first,second")


def test_client_uploads_files():
	def upload(req, ctx):
		photo = req.files["photo"]
		return Response.text(
			f"{req.input["caption"]}|{photo.filename}|{photo.content_type}|"
			f"{photo.content.decode()}"
		)

	client = make_client([Route(Method.POST, Pattern("/photos"), upload)])

	res = client.post(
		"/photos",
		form={
			"caption": "Beach",
			"photo": (BytesIO(b"image bytes"), "beach.jpg", "image/jpeg"),
		},
	)

	assert_eq(res.text, "Beach|beach.jpg|image/jpeg|image bytes")


def test_client_downloads_files():
	def download(req, ctx):
		return Response.file(b"\x00\xff", "data.bin", "application/octet-stream")

	client = make_client([Route(Method.GET, Pattern("/data"), download)])

	res = client.get("/data")

	assert_eq(res.data, b"\x00\xff")
	assert_eq(res.headers["Content-Type"], "application/octet-stream")
	assert_eq(res.headers["Content-Disposition"], 'attachment; filename="data.bin"')
	assert_eq(res.headers["Content-Length"], "2")


def test_client_retains_response_cookies():
	token = "fd3e6aff6360af4d6ba905d4299cff81"

	def remember(req, ctx):
		res = Response.empty()
		res.cookies["token"] = token
		return res

	def recall(req, ctx):
		return Response.text(req.cookies["token"].val)

	client = make_client(
		[
			Route(Method.GET, Pattern("/remember"), remember),
			Route(Method.GET, Pattern("/recall"), recall),
		]
	)

	client.get("/remember")
	res = client.get("/recall")

	assert_eq(res.text, token)
	assert_eq(client.get_cookie("token").value, token)


def test_client_manages_cookies():
	client = make_client([])
	token = "fd3e6aff6360af4d6ba905d4299cff81"

	client.set_cookie("token", token)
	cookie = client.get_cookie("token")

	assert_eq(cookie.value, token)

	client.delete_cookie("token")

	assert_that(client.get_cookie("token") is None)


def test_client_follows_redirects():
	def index(req, ctx):
		return Response.html("<h1>Index</h1>")

	def create(req, ctx):
		return Response.redirect(URL("/"))

	client = make_client(
		[
			Route(Method.GET, Pattern("/"), index),
			Route(Method.POST, Pattern("/"), create),
		]
	)

	redirect = client.post("/")
	followed = client.post("/", redirect=True)

	assert_eq(redirect.status_code, 302)
	assert_eq(redirect.headers["Location"], "/")
	assert_eq(redirect.history, ())

	assert_eq(followed.status_code, 200)
	assert_eq(followed.text, "<h1>Index</h1>")
	assert_eq(len(followed.history), 1)
	assert_eq(followed.history[0].status_code, 302)


def test_client_submits_method_override():
	def delete(req, ctx, id):
		return Response.text(f"{req.method.value}|{"_method" in req.input}")

	client = make_client([Route(Method.DELETE, Pattern("/posts/{id}"), delete)])

	res = client.post("/posts/1234", form={"_method": "DELETE"})

	assert_eq(res.text, "DELETE|False")


def make_client(routes):
	app = Application(helios.app.Config(), Router(routes), [])
	return TestClient(app)
