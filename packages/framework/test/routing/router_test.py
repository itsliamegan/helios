from uuid import UUID

from luna.test.assertion import assert_eq, assert_raises

from helios.app import Container, Context
from helios.http import Method, Request, Response, Status
from helios.routing import (
	Group,
	Match,
	Route,
	RouteNotFoundError,
	Router,
)
from helios.url import Pattern, URL


def handle(req, ctx):
	return Response.empty()


def context(request: Request) -> Context:
	return Context(Container(), request)


def test_dispatches_directly():
	def handler(req, ctx):
		return Response.empty(Status.OK)

	router = Router([Route.get("/", handler)])
	request = Request(Method.GET, URL("/"))
	res = router(request, context(request))

	assert_eq(res.status, Status.OK)


def test_routes_to_root():
	route = Route.get("/", handle)
	router = Router([route])

	match = router.match(Method.GET, URL("/"))

	assert_eq(match, Match(route, {}))


def test_routes_by_path():
	articles = Route.get("/articles/", handle)
	comments = Route.get("/comments/", handle)
	router = Router([articles, comments])

	articles_match = router.match(Method.GET, URL("/articles/"))
	comments_match = router.match(Method.GET, URL("/comments/"))

	assert_eq(articles_match, Match(articles, {}))
	assert_eq(comments_match, Match(comments, {}))


def test_routes_by_method():
	index = Route.get("/articles/", handle)
	store = Route.post("/articles/", handle)
	router = Router([index, store])

	index_match = router.match(Method.GET, URL("/articles/"))
	store_match = router.match(Method.POST, URL("/articles/"))

	assert_eq(index_match, Match(index, {}))
	assert_eq(store_match, Match(store, {}))


def test_routes_with_parameters():
	route = Route.get("/articles/{slug}", handle)
	router = Router([route])

	match = router.match(Method.GET, URL("/articles/intro"))

	assert_eq(match, Match(route, {"slug": "intro"}))


def test_routes_with_explicit_str_converter():
	route = Route.get("/articles/{slug:str}", handle)
	router = Router([route])

	match = router.match(Method.GET, URL("/articles/intro"))

	assert_eq(match, Match(route, {"slug": "intro"}))


def test_routes_with_uuid_converter():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	route = Route.get("/articles/{id:uuid}", handle)
	router = Router([route])

	match = router.match(Method.GET, URL(f"/articles/{id}"))

	assert_eq(match, Match(route, {"id": id}))


def test_passes_converted_parameters_to_handler_by_name():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	called_with = []

	def handler(req, ctx, slug: str, id: UUID):
		called_with.append((slug, id))
		return Response.empty(Status.OK)

	router = Router([Route.get("/articles/{id:uuid}/{slug}", handler)])

	request = Request(Method.GET, URL(f"/articles/{id}/intro"))
	router(request, context(request))

	assert_eq(called_with, [("intro", id)])


def test_uuid_converter_doesnt_match_invalid_uuid():
	pattern = Pattern.parse("/posts/{id:uuid}")

	match = pattern.match(URL("/posts/not-a-uuid"))

	assert_eq(match, None)


def test_matches_pattern_text_literally():
	pattern = Pattern.parse("/posts.json")

	assert_eq(pattern.match(URL("/posts.json")), {})
	assert_eq(pattern.match(URL("/postsXjson")), None)


def test_rejects_segments_mixing_text_and_parameters():
	with assert_raises(ValueError):
		Pattern.parse("/posts/draft-{id}")


def test_builds_routes_for_each_method():
	routes = [
		Route.get("/posts", handle),
		Route.post("/posts", handle),
		Route.put("/posts/{id:uuid}", handle),
		Route.patch("/posts/{id:uuid}", handle),
		Route.delete("/posts/{id:uuid}", handle),
	]

	assert_eq(
		[route.method for route in routes],
		[Method.GET, Method.POST, Method.PUT, Method.PATCH, Method.DELETE],
	)
	assert_eq(routes[2].pattern, Pattern.parse("/posts/{id:uuid}"))


def test_routes_instead_of_param():
	new = Route.get("/articles/new", handle)
	show = Route.get("/articles/{slug}", handle)
	router = Router([new, show])

	match = router.match(Method.GET, URL("/articles/new"))

	assert_eq(match, Match(new, {}))


def test_routes_with_param_to_subroute():
	route = Route.post("/articles/{slug}/read", handle)
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

	router = Router([Route.get("/", handler, guards=[first, second])])
	request = Request(Method.GET, URL("/"))
	router(request, context(request))

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

	router = Router([Route.get("/", handler, guards=[stop, later])])
	request = Request(Method.GET, URL("/"))
	res = router(request, context(request))

	assert_eq(res.status, Status.FORBIDDEN)
	assert_eq(calls, ["stop"])


def test_passes_converted_parameters_to_guards_by_name():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	called_with = []

	def guard(req, ctx, id: UUID):
		called_with.append(id)

	def handler(req, ctx, id: UUID):
		return Response.empty(Status.OK)

	router = Router([Route.get("/articles/{id:uuid}", handler, guards=[guard])])
	request = Request(Method.GET, URL(f"/articles/{id}"))
	router(request, context(request))

	assert_eq(called_with, [id])


def test_doesnt_run_guards_for_unmatched_routes():
	calls = []

	def guard(req, ctx):
		calls.append("guard")

	router = Router([Route.get("/articles", handle, guards=[guard])])
	match = router.match(Method.GET, URL("/missing"))

	assert_eq(match, None)
	assert_eq(calls, [])


def test_generates_named_grouped_route():
	router = Router(
		[
			Group(
				prefix="/posts",
				routes=[
					Route.get(
						"/{id:uuid}/edit",
						lambda req, ctx: Response.empty(),
						name="posts.edit",
					)
				],
			)
		]
	)
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	path = router.path("posts.edit", {"id": id})

	assert_eq(path, f"/posts/{id}/edit")


def test_rejects_generated_parameters_outside_route_syntax():
	router = Router(
		[
			Route.get(
				"/articles/{slug}",
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
			Route.get(
				"/articles/{slug}",
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
			Route.get(
				"/articles/{id:uuid}",
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
				Route.get(
					"/",
					lambda req, ctx: Response.empty(),
					name="home",
				),
				Route.get(
					"/other",
					lambda req, ctx: Response.empty(),
					name="home",
				),
			]
		)


def test_match_is_named_exactly():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	assert_eq(match.named("posts.show"), True)


def test_match_isnt_named_by_other_name():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	assert_eq(match.named("posts.index"), False)


def test_match_is_named_by_prefix():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	assert_eq(match.named("posts.*"), True)


def test_prefix_matches_nested_names():
	route = Route.get("/posts/{id}/comments", handle, name="posts.comments.index")
	match = Match(route, {})

	assert_eq(match.named("posts.*"), True)


def test_prefix_doesnt_match_bare_prefix():
	match = Match(Route.get("/posts", handle, name="posts"), {})

	assert_eq(match.named("posts.*"), False)


def test_match_is_named_by_any_pattern():
	match = Match(Route.get("/comments/{id}", handle, name="comments.show"), {})

	assert_eq(match.named("posts.*", "comments.*"), True)


def test_unnamed_match_isnt_named():
	match = Match(Route.get("/posts", handle), {})

	assert_eq(match.named("posts.index", "posts.*"), False)


def test_rejects_wildcard_before_suffix():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	with assert_raises(ValueError):
		match.named("*.show")


def test_rejects_wildcard_without_dot():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	with assert_raises(ValueError):
		match.named("posts*")


def test_rejects_wildcard_without_prefix():
	match = Match(Route.get("/posts/{id}", handle, name="posts.show"), {})

	with assert_raises(ValueError):
		match.named(".*")


def test_rejects_invalid_pattern_for_unnamed_route():
	match = Match(Route.get("/posts", handle), {})

	with assert_raises(ValueError):
		match.named("*.show")
