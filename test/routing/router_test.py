from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.http import Method, Request, Response, Status, URL
from helios.routing import (
	Group,
	Match,
	Pattern,
	Route,
	RouteNotFoundError,
	Router,
)


def test_dispatches_directly():
	def handler(req, ctx):
		return Response.empty(Status.OK)

	router = Router([Route(Method.GET, Pattern("/"), handler)])
	res = router(Request(Method.GET, URL("/")), None)

	assert_eq(res.status, Status.OK)


def test_routes_to_root():
	handler = object()
	route = Route(Method.GET, Pattern("/"), handler)
	router = Router([route])

	match = router.match(Method.GET, URL("/"))

	assert_eq(match, Match(route, {}))


def test_routes_by_path():
	articles = Route(Method.GET, Pattern("/articles/"), object())
	comments = Route(Method.GET, Pattern("/comments/"), object())
	router = Router([articles, comments])

	articles_match = router.match(Method.GET, URL("/articles/"))
	comments_match = router.match(Method.GET, URL("/comments/"))

	assert_eq(articles_match, Match(articles, {}))
	assert_eq(comments_match, Match(comments, {}))


def test_routes_by_method():
	index = Route(Method.GET, Pattern("/articles/"), object())
	store = Route(Method.POST, Pattern("/articles/"), object())
	router = Router([index, store])

	index_match = router.match(Method.GET, URL("/articles/"))
	store_match = router.match(Method.POST, URL("/articles/"))

	assert_eq(index_match, Match(index, {}))
	assert_eq(store_match, Match(store, {}))


def test_routes_with_params():
	route = Route(Method.GET, Pattern("/articles/{slug}"), object())
	router = Router([route])

	match = router.match(Method.GET, URL("/articles/intro"))

	assert_eq(match, Match(route, {"slug": "intro"}))


def test_routes_with_explicit_str_converter():
	route = Route(Method.GET, Pattern("/articles/{slug:str}"), object())
	router = Router([route])

	match = router.match(Method.GET, URL("/articles/intro"))

	assert_eq(match, Match(route, {"slug": "intro"}))


def test_routes_with_uuid_converter():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	route = Route(Method.GET, Pattern("/articles/{id:uuid}"), object())
	router = Router([route])

	match = router.match(Method.GET, URL(f"/articles/{id}"))

	assert_eq(match, Match(route, {"id": id}))


def test_passes_converted_params_to_handler_by_name():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	called_with = []

	def handler(req, ctx, slug: str, id: UUID):
		called_with.append((slug, id))
		return Response.empty(Status.OK)

	router = Router([Route(Method.GET, Pattern("/articles/{id:uuid}/{slug}"), handler)])

	router(Request(Method.GET, URL(f"/articles/{id}/intro")), None)

	assert_eq(called_with, [("intro", id)])


def test_uuid_converter_doesnt_match_invalid_uuid():
	pattern = Pattern("/boards/{id:uuid}")

	match = pattern.match(URL("/boards/not-a-uuid"))

	assert_that(match is None)


def test_routes_instead_of_param():
	new = Route(Method.GET, Pattern("/articles/new"), object())
	show = Route(Method.GET, Pattern("/articles/{slug}"), object())
	router = Router([new, show])

	match = router.match(Method.GET, URL("/articles/new"))

	assert_eq(match, Match(new, {}))


def test_routes_with_param_to_subroute():
	route = Route(Method.POST, Pattern("/articles/{slug}/read"), object())
	router = Router([route])

	match = router.match(Method.POST, URL("/articles/intro/read"))

	assert_eq(match, Match(route, {"slug": "intro"}))


def test_runs_route_guards_in_order_before_handler():
	calls = []

	def first(req, ctx):
		calls.append("first")

	def second(req, ctx):
		calls.append("second")

	def handler(req, ctx):
		calls.append("handler")
		return Response.empty(Status.OK)

	router = Router([Route(Method.GET, Pattern("/"), handler, guards=[first, second])])
	router(Request(Method.GET, URL("/")), None)

	assert_eq(calls, ["first", "second", "handler"])


def test_guard_response_stops_dispatch():
	calls = []

	def stop(req, ctx):
		calls.append("stop")
		return Response.text("Stopped", Status.FORBIDDEN)

	def later(req, ctx):
		calls.append("later")

	def handler(req, ctx):
		calls.append("handler")
		return Response.empty(Status.OK)

	router = Router([Route(Method.GET, Pattern("/"), handler, guards=[stop, later])])
	res = router(Request(Method.GET, URL("/")), None)

	assert_eq(res.status, Status.FORBIDDEN)
	assert_eq(calls, ["stop"])


def test_passes_converted_params_to_guards_by_name():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	called_with = []

	def guard(req, ctx, id: UUID):
		called_with.append(id)

	def handler(req, ctx, id: UUID):
		return Response.empty(Status.OK)

	router = Router(
		[Route(Method.GET, Pattern("/articles/{id:uuid}"), handler, guards=[guard])]
	)
	router(Request(Method.GET, URL(f"/articles/{id}")), None)

	assert_eq(called_with, [id])


def test_doesnt_run_guards_for_unmatched_routes():
	calls = []

	def guard(req, ctx):
		calls.append("guard")

	router = Router([Route(Method.GET, Pattern("/articles"), object(), guards=[guard])])
	match = router.match(Method.GET, URL("/missing"))

	assert_that(match is None)
	assert_eq(calls, [])


def test_generates_named_grouped_route():
	router = Router(
		[
			Group(
				prefix="/boards",
				routes=[
					Route(
						Method.GET,
						Pattern("/{id:uuid}/edit"),
						lambda req, ctx: Response.empty(),
						name="boards.edit",
					)
				],
			)
		]
	)
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	path = router.path("boards.edit", {"id": id})

	assert_eq(path, f"/boards/{id}/edit")


def test_rejects_generated_params_outside_route_syntax():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/articles/{slug}"),
				lambda req, ctx: Response.empty(),
				name="articles.show",
			)
		]
	)

	with assert_raises(ValueError):
		router.path("articles.show", {"slug": "today news"})


def test_rejects_invalid_route_generation():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/articles/{slug}"),
				lambda req, ctx: Response.empty(),
				name="articles.show",
			)
		]
	)

	with assert_raises(RouteNotFoundError):
		router.path("missing")
	with assert_raises(ValueError):
		router.path("articles.show")
	with assert_raises(ValueError):
		router.path("articles.show", {"slug": "intro", "extra": "value"})

	uuid_router = Router(
		[
			Route(
				Method.GET,
				Pattern("/articles/{id:uuid}"),
				lambda req, ctx: Response.empty(),
				name="articles.uuid",
			)
		]
	)
	with assert_raises(ValueError):
		uuid_router.path("articles.uuid", {"id": "not-a-uuid"})


def test_rejects_duplicate_route_names():
	with assert_raises(ValueError):
		Router(
			[
				Route(
					Method.GET,
					Pattern("/"),
					lambda req, ctx: Response.empty(),
					name="home",
				),
				Route(
					Method.GET,
					Pattern("/other"),
					lambda req, ctx: Response.empty(),
					name="home",
				),
			]
		)
