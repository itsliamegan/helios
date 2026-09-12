import multiprocessing
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises, assert_that

import helios.app
from helios.app import Application
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.persist.component import Component
from helios.persist.config import Config
from helios.persist.files import Files
from helios.routing import Pattern, Route, Router


def increment_in_process(
	path: Path,
	lock_path: Path,
	entered,
	release,
):
	files = Files(Config(lock_path))
	with files.lock():
		value = int(path.read_text())
		entered.set()
		release.wait()
		path.write_text(str(value + 1))


class IntegerFormat:
	def encode(self, value):
		return value

	def decode(self, value):
		return int(value)


class ListFormat:
	def encode(self, value):
		return value

	def decode(self, value):
		return list(value)


def test_opens_file_from_active_scope():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value.json")
		path.write_text("1")
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(path, IntegerFormat())

		with files.lock() as scope:
			handle = scope.open(file)

			assert_eq(handle.load(), 1)


def test_reuses_handle_for_same_file():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value.json")
		path.write_text("1")
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(path, IntegerFormat())

		with files.lock() as scope:
			first = scope.open(file)
			second = scope.open(file)

			assert_that(first is second)


def test_opens_distinct_handles_for_different_files():
	with TemporaryDirectory() as dir:
		files = Files(Config(Path(dir, "persistence.lock")))
		first_file = files.json(Path(dir, "first.json"), IntegerFormat())
		second_file = files.json(Path(dir, "second.json"), IntegerFormat())

		with files.lock() as scope:
			first = scope.open(first_file)
			second = scope.open(second_file)

			assert_that(first is not second)


def test_caches_loaded_value():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value.json")
		path.write_text("[]")
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(path, ListFormat())

		with files.lock() as scope:
			handle = scope.open(file)
			first = handle.load()
			second = handle.load()

			assert_that(first is second)


def test_save_replaces_cached_value():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value.json")
		path.write_text("[]")
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(path, ListFormat())
		saved = [1]

		with files.lock() as scope:
			handle = scope.open(file)
			handle.load()
			handle.save(saved)

			assert_that(handle.load() is saved)


def test_rejects_open_outside_scope():
	with TemporaryDirectory() as dir:
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(Path(dir, "value.json"), IntegerFormat())
		scope = files.lock()

		with assert_raises(RuntimeError):
			scope.open(file)


def test_rejects_handle_after_scope_closes():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value.json")
		path.write_text("1")
		files = Files(Config(Path(dir, "persistence.lock")))
		file = files.json(path, IntegerFormat())

		with files.lock() as scope:
			handle = scope.open(file)

		with assert_raises(RuntimeError):
			handle.load()


def test_rejects_file_from_different_files():
	with TemporaryDirectory() as dir:
		first = Files(Config(Path(dir, "first.lock")))
		second = Files(Config(Path(dir, "second.lock")))
		file = second.json(Path(dir, "value.json"), IntegerFormat())

		with first.lock() as scope, assert_raises(RuntimeError):
			scope.open(file)


def test_lock_serializes_writes():
	with TemporaryDirectory() as dir:
		path = Path(dir, "value")
		lock_path = Path(dir, "persistence.lock")
		path.write_text("0")
		context = multiprocessing.get_context("fork")
		first_entered = context.Event()
		first_release = context.Event()
		second_entered = context.Event()
		second_release = context.Event()
		second_release.set()
		first = context.Process(
			target=increment_in_process,
			args=(path, lock_path, first_entered, first_release),
		)
		second = context.Process(
			target=increment_in_process,
			args=(path, lock_path, second_entered, second_release),
		)

		first.start()
		assert_that(first_entered.wait(1))
		second.start()
		assert_that(not second_entered.wait(0.05))
		first_release.set()
		first.join(2)
		second.join(2)

		assert_eq(first.exitcode, 0)
		assert_eq(second.exitcode, 0)
		assert_eq(path.read_text(), "2")


def run_request(
	lock_path: Path,
	entered,
	release,
):
	def hold(req, ctx):
		entered.set()
		release.wait()
		return Response.empty(Status.OK)

	app = Application(
		helios.app.Config(),
		Router([Route(Method.GET, Pattern("/"), hold)]),
		[Component(Files(Config(lock_path)))],
	)
	res = app.handle(Request(Method.GET, URL("/"), Headers(), Input()))
	if res.status is not Status.OK:
		raise RuntimeError(f"request failed with {res.status}")


def test_app_serializes_requests():
	with TemporaryDirectory() as dir:
		lock_path = Path(dir, "persistence.lock")
		context = multiprocessing.get_context("fork")
		first_entered = context.Event()
		first_release = context.Event()
		second_entered = context.Event()
		second_release = context.Event()
		second_release.set()
		first = context.Process(
			target=run_request,
			args=(lock_path, first_entered, first_release),
		)
		second = context.Process(
			target=run_request,
			args=(lock_path, second_entered, second_release),
		)

		first.start()
		assert_that(first_entered.wait(1))
		second.start()
		assert_that(not second_entered.wait(0.05))
		first_release.set()
		first.join(2)
		second.join(2)

		assert_eq(first.exitcode, 0)
		assert_eq(second.exitcode, 0)
