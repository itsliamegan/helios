from luna.test.assertion import assert_eq, assert_is, assert_is_not, assert_not_none

from helios.app import Container, Context
from helios.http import Method, Request, URL


class Post:
	pass


class Author:
	pass


def request() -> Request:
	return Request(Method.GET, URL("/"))


def test_resolves_each_binding_lifetime():
	created = []
	container = Container()
	container.instance(str, "instance")
	container.singleton(list, lambda container: [])
	container.scoped(dict, lambda context: created.append(context) or {})

	first = Context(container, request())
	second = Context(container, request())

	assert_eq(first.get(str), "instance")
	assert_is(first.get(list), first.get(list))
	assert_is(first.get(dict), first.get(dict))
	assert_is(second.get(list), first.get(list))
	assert_is_not(second.get(dict), first.get(dict))
	assert_eq(len(created), 2)


def test_later_registration_replaces_binding_lifetime():
	container = Container()
	container.instance(str, "old")
	container.scoped(str, lambda context: "new")
	context = Context(container, request())

	assert_eq(context.get(str), "new")


def test_resolved_does_not_construct_lazy_services():
	seen = []
	container = Container()
	container.singleton(list, lambda container: seen.append("singleton") or [])
	container.scoped(dict, lambda context: seen.append("scoped") or {})
	context = Context(container, request())

	assert_eq(context.resolved(list), None)
	assert_eq(context.resolved(dict), None)
	context.get(dict)

	assert_not_none(context.resolved(dict))
	assert_eq(seen, ["scoped"])


def test_resolves_parameterized_keys_by_their_class():
	container = Container()
	container.scoped(dict, lambda context: {})
	context = Context(container, request())

	assert_eq(context.resolved(dict[str, int]), None)
	value = context.get(dict[str, int])

	assert_is(context.get(dict), value)
	assert_is(context.resolved(dict[str, str]), value)


def test_releases_yielding_scoped_service_when_closed():
	events = []
	container = Container()

	def post(context):
		events.append("acquire")
		yield Post()
		events.append("release")

	container.scoped(Post, post)
	context = Context(container, request())
	context.get(Post)

	assert_eq(events, ["acquire"])
	context.close()

	assert_eq(events, ["acquire", "release"])


def test_releases_scoped_services_before_their_dependencies():
	events = []
	container = Container()

	def author(context):
		yield Author()
		events.append("author")

	def post(context):
		context.get(Author)
		yield Post()
		events.append("post")

	container.scoped(Author, author)
	container.scoped(Post, post)
	context = Context(container, request())
	context.get(Post)
	context.close()

	assert_eq(events, ["post", "author"])


def test_builds_yielding_scoped_service_once_per_context():
	calls = []
	container = Container()

	def post(context):
		calls.append(context)
		yield Post()

	container.scoped(Post, post)
	first = Context(container, request())
	second = Context(container, request())

	assert_is(first.get(Post), first.get(Post))
	assert_is_not(second.get(Post), first.get(Post))
	assert_eq(len(calls), 2)
