from collections.abc import Generator
from contextlib import contextmanager, redirect_stderr
from io import StringIO
from pathlib import Path
import sys
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that
from watchfiles import Change

import helios.app
import helios.assets.config
import helios.assets.provider
from helios.console import Program
from helios.routing import Router
from helios.url import URL
import helios.view.config
import helios.view.provider
from helios.wsgi import Application
from helios.wsgi.command import Filter, Serve


@contextmanager
def command_line(argv: list[str]) -> Generator[None]:
	previous = sys.argv
	sys.argv = argv
	try:
		yield
	finally:
		sys.argv = previous


def application(
	base_url: URL | None = None,
	views: Path | None = None,
	assets: Path | None = None,
) -> Application:
	providers = []
	if assets is not None:
		providers.append(
			helios.assets.provider.Provider(
				helios.assets.config.Config(
					assets,
					Path("public", "assets"),
					scripts=[],
					styles=[],
				)
			)
		)
	if views is not None:
		providers.append(
			helios.view.provider.Provider(helios.view.config.Config(views))
		)
	return Application(helios.app.Config(base_url), Router([]), providers)


def failure(application: Application) -> tuple[int | str | None, str]:
	stderr = StringIO()
	with redirect_stderr(stderr), assert_raises(SystemExit) as raised:
		Program.main(["serve"], application)
	return raised.exception.code, stderr.getvalue()


def test_child_runs_the_command_line_again_without_reloading():
	script = f"bin/{uuid4().hex}.py"
	serve = Serve(application())

	with command_line([script, "serve"]):
		child = serve.child()

	assert_eq(child, [sys.executable, script, "serve", "--no_reload"])


def test_filter_passes_python_files():
	root = Path("/", uuid4().hex)
	filter = Filter([])

	assert_that(filter(Change.modified, str(Path(root, "app", "post.py"))))


def test_filter_passes_any_file_under_a_watched_directory():
	views = Path("/", uuid4().hex, "app", "views")
	filter = Filter([views])

	assert_that(filter(Change.added, str(Path(views, "posts", "index.html"))))


def test_filter_ignores_other_files():
	root = Path("/", uuid4().hex)
	filter = Filter([Path(root, "app", "views")])

	assert_that(not filter(Change.modified, str(Path(root, "public", "app.css"))))


def test_filter_ignores_python_files_in_ignored_directories():
	root = Path("/", uuid4().hex)
	filter = Filter([])

	assert_that(not filter(Change.modified, str(Path(root, ".venv", "site.py"))))


def test_serve_watches_the_views_directory_under_the_root():
	root = Path("/", uuid4().hex)
	serve = Serve(application(views=Path("app", "views")))

	filter = serve.filter(root)

	assert_eq(filter.directories, [Path(root, "app", "views")])


def test_serve_watches_the_assets_directory_under_the_root():
	root = Path("/", uuid4().hex)
	serve = Serve(application(assets=Path("app", "assets")))

	filter = serve.filter(root)

	assert_eq(filter.directories, [Path(root, "app", "assets")])


def test_serve_watches_no_directory_without_views():
	serve = Serve(application())

	filter = serve.filter(Path("/", uuid4().hex))

	assert_eq(filter.directories, [])


def test_serve_fails_without_a_base_url():
	code, stderr = failure(application())

	assert_eq(code, 1)
	assert_that(stderr.startswith("helios: error: "))


def test_serve_fails_without_a_port_in_the_base_url():
	code, stderr = failure(application(URL.parse("http://localhost")))

	assert_eq(code, 1)
	assert_that(stderr.startswith("helios: error: "))
