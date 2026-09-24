from uuid import UUID

from luna.test.assertion import assert_eq, assert_that

from helios.http import Method, Request, Response, Status, URL
from helios.routing import (
	Group,
	Pattern,
	Route,
	Router,
)


def test_calling_route_runs_guards_before_handler():
	calls = []

	def guard(req, ctx, id):
		calls.append(("guard", id))

	def handler(req, ctx, id):
		calls.append(("handler", id))
		return Response.empty(Status.OK)

	route = Route(Method.GET, Pattern("/{id}"), handler, [guard])
	res = route(Request(Method.GET, URL("/1")), None, id="1")

	assert_eq(res.status, Status.OK)
	assert_eq(calls, [("guard", "1"), ("handler", "1")])


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
