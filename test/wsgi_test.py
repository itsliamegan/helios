from werkzeug.test import EnvironBuilder

from helios.http import Body, Cookies, Headers, Method, Response, Status
from helios.wsgi import adapt_env, adapt_res

def test_adapts_method():
	env = EnvironBuilder(method="GET").get_environ()

	req = adapt_env(env)

	assert req.method is Method.GET

def test_adapts_url():
	env = EnvironBuilder(path = "/search?q=Intro").get_environ()

	req = adapt_env(env)

	assert req.url.path == "/search"
	assert req.url.query == {"q": "Intro"}

def test_adapts_headers():
	env = EnvironBuilder(headers = [("Accept", "text/html"), ("User-Agent", "Mozilla/5.0")]).get_environ()

	req = adapt_env(env)

	assert str(req.headers["Accept"]) == "text/html"
	assert str(req.headers["User-Agent"]) == "Mozilla/5.0"

def test_adapts_content_info():
	env = EnvironBuilder(content_type = "text/html", content_length = "100").get_environ()

	req = adapt_env(env)

	assert str(req.headers["Content-Type"]) == "text/html"
	assert str(req.headers["Content-Length"]) == "100"

def test_adapts_form_input():
	env = EnvironBuilder(data = {"content": "An interesting article."}).get_environ()

	req = adapt_env(env)

	assert req.input["content"] == "An interesting article."

def test_adapts_res():
	res = Response(
		Status.OK,
		Headers({"Content-Type": "text/html"}),
		Cookies({"session_id": "51d0d53a-11dd-47a5-b438-5eb1b84e1432"}),
		Body("<h1>Index</h1>")
	)

	def start_res(status, pairs):
		assert status == "200 OK"
		assert pairs == [
			("Content-Type", "text/html"),
			("Set-Cookie", "session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/")
		]

	body = adapt_res(res, start_res)

	assert list(body) == ["<h1>Index</h1>".encode("utf8")]

def test_adapts_multiple_cookies():
	res = Response.empty()
	res.cookies["session_id"] = "51d0d53a-11dd-47a5-b438-5eb1b84e1432"
	res.cookies["csrf_token"] = "fd3e6aff6360af4d6ba905d4299cff81"

	def start_res(status, pairs):
		assert pairs == [
			("Set-Cookie", "session_id=51d0d53a-11dd-47a5-b438-5eb1b84e1432; Path=/"),
			("Set-Cookie", "csrf_token=fd3e6aff6360af4d6ba905d4299cff81; Path=/")
		]

	adapt_res(res, start_res)
