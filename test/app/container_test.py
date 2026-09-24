from concurrent.futures import ThreadPoolExecutor

from luna.test.assertion import assert_eq, assert_raises

from helios.app import Container, DependencyError


def test_reports_missing_and_scoped_dependencies():
	container = Container()
	container.singleton(str, lambda container: container.get(int))

	with assert_raises(DependencyError) as raised:
		container.get(str)
	assert "int" in str(raised.exception)

	container.scoped(str, lambda context: "value")

	with assert_raises(DependencyError) as raised:
		container.get(str)
	assert "request context" in str(raised.exception)


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
	assert all(value is values[0] for value in values)
