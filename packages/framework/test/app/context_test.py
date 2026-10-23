from luna.test.assertion import (
	assert_eq,
	assert_is,
	assert_is_instance,
	assert_is_not,
	assert_not_none,
	assert_raises,
)

from helios.app import Container, Context
from helios.http import Method, Request
from helios.url import URL


class Visit:
	pass


class Reader:
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

	def visit(context):
		events.append("acquire")
		yield Visit()
		events.append("release")

	container.scoped(Visit, visit)
	with Context(container, request()) as context:
		context.get(Visit)
		assert_eq(events, ["acquire"])

	assert_eq(events, ["acquire", "release"])


def test_releases_scoped_services_before_their_dependencies():
	events = []
	container = Container()

	def reader(context):
		yield Reader()
		events.append("reader")

	def visit(context):
		context.get(Reader)
		yield Visit()
		events.append("visit")

	container.scoped(Reader, reader)
	container.scoped(Visit, visit)
	with Context(container, request()) as context:
		context.get(Visit)

	assert_eq(events, ["visit", "reader"])


def test_builds_yielding_scoped_service_once_per_context():
	calls = []
	container = Container()

	def visit(context):
		calls.append(context)
		yield Visit()

	container.scoped(Visit, visit)
	first = Context(container, request())
	second = Context(container, request())

	assert_is(first.get(Visit), first.get(Visit))
	assert_is_not(second.get(Visit), first.get(Visit))
	assert_eq(len(calls), 2)


def test_yielding_factory_sees_no_error_on_success():
	seen = []
	container = Container()

	def visit(context):
		try:
			yield Visit()
		except BaseException as error:
			seen.append(error)
			raise
		else:
			seen.append(None)

	container.scoped(Visit, visit)
	with Context(container, request()) as context:
		context.get(Visit)

	assert_eq(seen, [None])


def test_yielding_factory_sees_recorded_failure():
	seen = []
	failure = ValueError("failed")
	container = Container()

	def visit(context):
		try:
			yield Visit()
		except BaseException as error:
			seen.append(error)
			raise

	container.scoped(Visit, visit)
	with Context(container, request()) as context:
		context.get(Visit)
		context.failure = failure

	assert_eq(len(seen), 1)
	assert_is(seen[0], failure)


def test_releases_with_escaped_exception_and_propagates_it():
	seen = []
	container = Container()

	def visit(context):
		try:
			yield Visit()
		except BaseException as error:
			seen.append(error)
			raise

	container.scoped(Visit, visit)
	context = Context(container, request())

	with assert_raises(KeyboardInterrupt), context:
		context.get(Visit)
		raise KeyboardInterrupt()
	assert_is_instance(seen[0], KeyboardInterrupt)
	assert_eq(context.failure, None)


def test_escaped_exception_takes_precedence_over_recorded_failure():
	seen = []
	container = Container()

	def visit(context):
		try:
			yield Visit()
		except BaseException as error:
			seen.append(error)
			raise

	container.scoped(Visit, visit)

	with assert_raises(KeyboardInterrupt), Context(container, request()) as context:
		context.get(Visit)
		context.failure = ValueError("failed")
		raise KeyboardInterrupt()
	assert_is_instance(seen[0], KeyboardInterrupt)


def test_rejects_resolving_from_closed_context():
	container = Container()
	container.scoped(Visit, lambda context: Visit())
	with Context(container, request()) as context:
		pass

	with assert_raises(RuntimeError):
		context.get(Visit)
