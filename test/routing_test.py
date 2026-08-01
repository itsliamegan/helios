from helios.http import Body, Headers, Input, Method, Request, Response, Status, URL
from helios.routing import Kernel, Pattern, Route, Router

def test_calls_middlewares():
	def middleware(req, ctx, next):
		res = next(req, ctx)
		res.headers["Content-Type"] = "text/plain"
		return res

	def handler(req, ctx):
		return Response.empty(Status.OK)

	kernel = Kernel([Route(Method.GET, Pattern("/"), handler)], [middleware])

	res = kernel.handle(Request(Method.GET, URL("/"), Headers(), Input()), None)

	assert str(res.headers["Content-Type"]) == "text/plain"


def test_routes_to_root():
	handler = object()
	router = Router([
		Route(Method.GET, Pattern("/"), handler)
	])

	match = router.match(Request(Method.GET, URL("/"), Headers(), Input()))

	assert match == (handler, {})

def test_routes_by_path():
	articles = object()
	comments = object()
	router = Router([
		Route(Method.GET, Pattern("/articles/"), articles),
		Route(Method.GET, Pattern("/comments/"), comments)
	])

	articles_match = router.match(Request(Method.GET, URL("/articles/"), Headers(), Input()))
	comments_match = router.match(Request(Method.GET, URL("/comments/"), Headers(), Input()))

	assert articles_match == (articles, {})
	assert comments_match == (comments, {})

def test_routes_by_method():
	index = object()
	store = object()
	router = Router([
		Route(Method.GET, Pattern("/articles/"), index),
		Route(Method.POST, Pattern("/articles/"), store)
	])

	index_match = router.match(Request(Method.GET, URL("/articles/"), Headers(), Input()))
	store_match = router.match(Request(Method.POST, URL("/articles/"), Headers(), Input()))

	assert index_match == (index, {})
	assert store_match == (store, {})

def test_routes_with_params():
	handler = object()
	router = Router([
		Route(Method.GET, Pattern("/articles/{slug}"), handler)
	])

	match = router.match(Request(Method.GET, URL("/articles/intro"), Headers(), Input()))

	assert match == (handler, {"slug": "intro"})

def test_routes_instead_of_param():
	new = object()
	show = object()
	router = Router([
		Route(Method.GET, Pattern("/articles/new"), new),
		Route(Method.GET, Pattern("/articles/{slug}"), show)
	])

	match = router.match(Request(Method.GET, URL("/articles/new"), Headers(), Input()))

	assert match == (new, {})

def test_routes_with_param_to_subroute():
	handler = object()
	router = Router([
		Route(Method.POST, Pattern("/articles/{slug}/read"), handler)
	])

	match = router.match(Request(Method.POST, URL("/articles/intro/read"), Headers(), Input()))

	assert match == (handler, {"slug": "intro"})
