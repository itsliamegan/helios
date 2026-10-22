from concurrent.futures import ThreadPoolExecutor

from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_is,
	assert_raises,
	assert_that,
)

from helios.app import Container, DependencyError


class Newsletter:
	pass


class Moderator:
	pass


def test_reports_missing_and_scoped_dependencies():
	container = Container()
	container.singleton(str, lambda container: container.get(int))

	with assert_raises(DependencyError) as raised:
		container.get(str)
	assert_in("int", str(raised.exception))

	container.scoped(str, lambda context: "value")

	with assert_raises(DependencyError) as raised:
		container.get(str)
	assert_in("request context", str(raised.exception))


def test_reports_bound_dependencies():
	container = Container()
	container.instance(int, 1)
	container.singleton(str, lambda container: "value")
	container.scoped(float, lambda context: 1.0)

	assert_eq(
		[
			container.bound(int),
			container.bound(str),
			container.bound(float),
			container.bound(bytes),
		],
		[True, True, True, False],
	)


def test_rejects_none_and_retries_failed_singleton_factories():
	container = Container()

	with assert_raises(DependencyError):
		container.instance(str, None)

	attempts = []

	def value(container):
		attempts.append(None)
		if len(attempts) == 1:
			raise ValueError("failed")
		return "ready"

	container.singleton(str, value)

	with assert_raises(ValueError):
		container.get(str)
	assert_eq(container.get(str), "ready")
	assert_eq(len(attempts), 2)


def test_constructs_one_singleton_across_threads():
	calls = []
	container = Container()

	def value(container):
		calls.append(None)
		return object()

	container.singleton(object, value)

	with ThreadPoolExecutor(max_workers=8) as executor:
		values = list(executor.map(lambda _: container.get(object), range(32)))

	assert_eq(len(calls), 1)
	assert_that(all(value is values[0] for value in values))


def test_constructs_one_yielding_singleton_across_threads():
	calls = []
	container = Container()

	def newsletter(container):
		calls.append(None)
		yield Newsletter()

	container.singleton(Newsletter, newsletter)

	with ThreadPoolExecutor(max_workers=8) as executor:
		newsletters = list(executor.map(lambda _: container.get(Newsletter), range(32)))

	assert_eq(len(calls), 1)
	assert_that(all(newsletter is newsletters[0] for newsletter in newsletters))


def test_releases_yielding_singleton_when_closed():
	events = []
	container = Container()

	def newsletter(container):
		events.append("acquire")
		yield Newsletter()
		events.append("release")

	container.singleton(Newsletter, newsletter)
	container.get(Newsletter)

	assert_eq(events, ["acquire"])
	container.close()

	assert_eq(events, ["acquire", "release"])


def test_releases_singletons_before_their_dependencies():
	events = []
	container = Container()

	def moderator(container):
		yield Moderator()
		events.append("moderator")

	def newsletter(container):
		container.get(Moderator)
		yield Newsletter()
		events.append("newsletter")

	container.singleton(Moderator, moderator)
	container.singleton(Newsletter, newsletter)
	container.get(Newsletter)
	container.close()

	assert_eq(events, ["newsletter", "moderator"])


def test_runs_remaining_cleanups_when_one_raises():
	events = []
	container = Container()

	def moderator(container):
		try:
			yield Moderator()
		finally:
			events.append("moderator")

	def newsletter(container):
		yield Newsletter()
		raise ValueError("failed")

	container.singleton(Moderator, moderator)
	container.singleton(Newsletter, newsletter)
	container.get(Moderator)
	container.get(Newsletter)

	with assert_raises(ValueError):
		container.close()
	assert_eq(events, ["moderator"])


def test_rejects_none_from_yielding_factory_and_releases_it():
	events = []
	container = Container()

	def newsletter(container):
		try:
			yield None
		finally:
			events.append("release")

	container.singleton(Newsletter, newsletter)

	with assert_raises(DependencyError):
		container.get(Newsletter)
	assert_eq(events, ["release"])


def test_rejects_resolving_from_closed_container():
	container = Container()
	container.singleton(Newsletter, lambda container: Newsletter())
	container.close()

	with assert_raises(RuntimeError):
		container.get(Newsletter)


def test_resolves_parameterized_keys_by_their_class():
	container = Container()
	container.singleton(list[int], lambda container: [1])

	assert_eq(
		[container.bound(list), container.bound(list[str])],
		[True, True],
	)
	assert_is(container.get(list[str]), container.get(list))
