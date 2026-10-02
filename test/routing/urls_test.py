from uuid import UUID

from luna.test.assertion import assert_eq, assert_that

from helios.http import Method, Query, Response, URL
from helios.routing import (
	Pattern,
	Route,
	Router,
	URLs,
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
	urls = URLs(router, URL.parse("https://cork.example:8443"))

	url = urls.route("redemptions.new", query={"token": "secret value"}, absolute=True)

	assert_eq(
		str(url),
		"https://cork.example:8443/redemptions/new?token=secret+value",
	)


def test_generates_route_with_query_object():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/posts/"),
				lambda req, ctx: Response.empty(),
				name="posts.index",
			)
		]
	)
	urls = URLs(router, URL.parse("https://cork.example"))

	url = urls.route("posts.index", query=Query({"tag": ["news", "politics"]}))

	assert_eq(str(url), "/posts/?tag=news&tag=politics")


def test_generates_relative_route_by_default():
	router = Router(
		[
			Route(
				Method.GET,
				Pattern("/posts/"),
				lambda req, ctx: Response.empty(),
				name="posts.index",
			)
		]
	)
	urls = URLs(router, URL.parse("https://cork.example"))

	url = urls.route("posts.index")

	assert_eq(str(url), "/posts/")


def matchable_urls():
	show = Route(
		Method.GET,
		Pattern("/posts/{id:uuid}"),
		lambda req, ctx, id: Response.empty(),
		name="posts.show",
	)
	update = Route(
		Method.POST,
		Pattern("/posts/{id:uuid}/title"),
		lambda req, ctx, id: Response.empty(),
		name="posts.update",
	)
	return URLs(Router([show, update]), URL.parse("https://cork.example"))


def test_matches_url_string_to_named_route():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"/posts/{id}?sort=recent")

	assert_that(match is not None)
	assert_eq(match.route.name, "posts.show")
	assert_eq(match.params, {"id": id})


def test_matches_url_object_to_named_route():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(URL(f"/posts/{id}"))

	assert_that(match is not None)
	assert_eq(match.route.name, "posts.show")
	assert_eq(match.params, {"id": id})


def test_matches_only_the_path_of_absolute_urls():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"https://elsewhere.example/posts/{id}")

	assert_that(match is not None)
	assert_eq(match.route.name, "posts.show")
	assert_eq(match.params, {"id": id})


def test_matches_url_string_with_url_in_query():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"/posts/{id}?return_to=https://elsewhere.example/")

	assert_that(match is not None)
	assert_eq(match.route.name, "posts.show")


def test_matches_only_get_routes():
	urls = matchable_urls()
	id = UUID("102ddad7-06d1-484f-a3f8-3cf4711e91ba")

	match = urls.match(f"/posts/{id}/title")

	assert_that(match is None)


def test_doesnt_match_missing_or_unknown_urls():
	urls = matchable_urls()

	missing = urls.match(None)
	unknown = urls.match("/posts/not-a-uuid")
	unparseable = urls.match("http://[invalid/posts/")
	hostless = urls.match("cork.example/posts/")

	assert_that(missing is None)
	assert_that(unknown is None)
	assert_that(unparseable is None)
	assert_that(hostless is None)
