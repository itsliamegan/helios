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
	URLs,
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


def test_group_without_prefix_or_guards_preserves_route_configuration():
	handler = object()
	route = Route(Method.GET, Pattern("/articles"), handler)

	effective = Router([Group(routes=[route])]).routes[0]

	assert_that(effective is route)
	assert_that(effective.method is Method.GET)
	assert_eq(effective.pattern.raw, "/articles")
	assert_that(effective.handler is handler)
	assert_eq(effective.guards, [])


def test_applies_group_prefix_to_direct_routes():
	router = Router(
		[
			Group(
				prefix="/articles",
				routes=[
					Route(Method.GET, Pattern("/"), object()),
					Route(Method.GET, Pattern("/new"), object()),
				],
			)
		]
	)

	assert_eq(
		[route.pattern.raw for route in router.routes],
		[
			"/articles/",
			"/articles/new",
		],
	)


def test_composes_nested_group_prefixes_and_trailing_slashes():
	router = Router(
		[
			Group(
				prefix="/articles/",
				routes=[
					Group(
						prefix="/comments",
						routes=[
							Route(Method.GET, Pattern("/"), object()),
							Route(Method.GET, Pattern("/{id:uuid}/"), object()),
						],
					),
				],
			)
		]
	)

	assert_eq(
		[route.pattern.raw for route in router.routes],
		[
			"/articles/comments/",
			"/articles/comments/{id:uuid}/",
		],
	)


def test_converts_params_in_grouped_patterns():
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")
	called_with = []

	def handler(req, ctx, id):
		called_with.append(id)
		return Response.empty(Status.OK)

	router = Router(
		[
			Group(
				prefix="/articles",
				routes=[
					Route(Method.GET, Pattern("/{id:uuid}"), handler),
				],
			)
		]
	)
	router(Request(Method.GET, URL(f"/articles/{id}")), None)

	assert_eq(called_with, [id])


def test_inherits_group_guards_into_every_descendant():
	def guard(req, ctx):
		pass

	router = Router(
		[
			Group(
				guards=[guard],
				routes=[
					Route(Method.GET, Pattern("/one"), object()),
					Group(routes=[Route(Method.GET, Pattern("/two"), object())]),
				],
			)
		]
	)

	assert_eq([route.guards for route in router.routes], [[guard], [guard]])
	assert_that(router.routes[0].guards is not router.routes[1].guards)


def test_runs_nested_and_route_guards_outermost_first():
	calls = []

	def outer(req, ctx):
		calls.append("outer")

	def inner(req, ctx):
		calls.append("inner")

	def route_guard(req, ctx):
		calls.append("route")

	def handler(req, ctx):
		calls.append("handler")
		return Response.empty(Status.OK)

	router = Router(
		[
			Group(
				guards=[outer],
				routes=[
					Group(
						guards=[inner],
						routes=[
							Route(
								Method.GET, Pattern("/"), handler, guards=[route_guard]
							),
						],
					),
				],
			)
		]
	)
	router(Request(Method.GET, URL("/")), None)

	assert_eq(calls, ["outer", "inner", "route", "handler"])


def test_inherited_guard_response_stops_dispatch():
	calls = []

	def outer(req, ctx):
		calls.append("outer")
		return Response.text("Forbidden", Status.FORBIDDEN)

	def inner(req, ctx):
		calls.append("inner")

	def handler(req, ctx):
		calls.append("handler")
		return Response.empty(Status.OK)

	router = Router(
		[
			Group(
				guards=[outer],
				routes=[
					Route(Method.GET, Pattern("/"), handler, guards=[inner]),
				],
			)
		]
	)
	res = router(Request(Method.GET, URL("/")), None)

	assert_eq(res.status, Status.FORBIDDEN)
	assert_eq(calls, ["outer"])


def test_group_flattening_preserves_declaration_and_matching_order():
	first = object()
	second = object()
	third = object()
	router = Router(
		[
			Group(
				routes=[
					Route(Method.GET, Pattern("/{slug}"), first),
					Route(Method.GET, Pattern("/new"), second),
				]
			),
			Route(Method.GET, Pattern("/{slug}"), third),
		]
	)

	assert_eq([route.handler for route in router.routes], [first, second, third])
	match = router.match(Method.GET, URL("/new"))
	assert_that(match is not None and match.route.handler is first)


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


def test_generates_absolute_route_with_query_explicitly():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/redemptions/new"),
				lambda req, ctx: Response.empty(),
				name="redemptions.new",
			)
		]
	)
	urls = URLs(router, URL("https://cork.example:8443"))

	url = urls.route("redemptions.new", query={"token": "secret value"}, absolute=True)

	assert_eq(
		str(url),
		"https://cork.example:8443/redemptions/new?token=secret+value",
	)


def test_generates_relative_route_by_default():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/boards/"),
				lambda req, ctx: Response.empty(),
				name="boards.index",
			)
		]
	)
	urls = URLs(router, URL("https://cork.example"))

	url = urls.route("boards.index")

	assert_eq(str(url), "/boards/")


def matchable_urls():
	show = Route(
		Method.GET,
		Pattern("/boards/{id:uuid}"),
		lambda req, ctx, id: Response.empty(),
		name="boards.show",
	)
	update = Route(
		Method.POST,
		Pattern("/boards/{id:uuid}/title"),
		lambda req, ctx, id: Response.empty(),
		name="boards.update",
	)
	return URLs(Router([show, update]), URL("https://cork.example"))


def test_matches_url_string_to_named_route():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"/boards/{id}?sort=recent")

	assert_that(match is not None)
	assert_eq(match.route.name, "boards.show")
	assert_eq(match.params, {"id": id})


def test_matches_url_object_to_named_route():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(URL(f"/boards/{id}"))

	assert_that(match is not None)
	assert_eq(match.route.name, "boards.show")
	assert_eq(match.params, {"id": id})


def test_matches_only_the_path_of_absolute_urls():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"https://elsewhere.example/boards/{id}")

	assert_that(match is not None)
	assert_eq(match.route.name, "boards.show")
	assert_eq(match.params, {"id": id})


def test_matches_only_get_routes():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"/boards/{id}/title")

	assert_that(match is None)


def test_doesnt_match_missing_or_unknown_urls():
	urls = matchable_urls()

	missing = urls.match(None)
	unknown = urls.match("/boards/not-a-uuid")
	unparseable = urls.match("http://[invalid/boards/")

	assert_that(missing is None)
	assert_that(unknown is None)
	assert_that(unparseable is None)


def test_reusing_group_configuration_doesnt_mutate_sources():
	def group_guard(req, ctx):
		pass

	def route_guard(req, ctx):
		pass

	route = Route(Method.GET, Pattern("/{id:uuid}/"), object(), guards=[route_guard])
	shared = Group(prefix="/items", guards=[group_guard], routes=[route])
	router = Router(
		[
			Group(prefix="/one", routes=[shared]),
			Group(prefix="/two", routes=[shared]),
		]
	)

	assert_eq(route.pattern.raw, "/{id:uuid}/")
	assert_eq(route.guards, [route_guard])
	assert_eq(shared.prefix, "/items")
	assert_eq(shared.guards, [group_guard])
	assert_eq(shared.routes, [route])
	assert_eq(
		[effective.pattern.raw for effective in router.routes],
		[
			"/one/items/{id:uuid}/",
			"/two/items/{id:uuid}/",
		],
	)
	assert_eq(router.routes[0].guards, [group_guard, route_guard])
	assert_eq(router.routes[1].guards, [group_guard, route_guard])
	assert_that(router.routes[0].guards is not router.routes[1].guards)
