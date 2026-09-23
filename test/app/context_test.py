from luna.test.assertion import assert_eq

from helios.app import Container, Context
from helios.http import Method, Request, URL


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
	assert first.get(list) is first.get(list)
	assert first.get(dict) is first.get(dict)
	assert second.get(list) is first.get(list)
	assert second.get(dict) is not first.get(dict)
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

	assert context.resolved(dict) is not None
	assert_eq(seen, ["scoped"])
