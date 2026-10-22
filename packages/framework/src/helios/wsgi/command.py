from pathlib import Path
import shlex
import signal
import sys
from typing import Any

from luna.cli import Command, option
from watchfiles import Change, DefaultFilter, run_process
from werkzeug.serving import run_simple

import helios.app
from helios.assets import Bundler, BundlerNotFoundError, CompileError
import helios.assets.config
import helios.view.config

from .application import Application


class Serve(Command):
	"""Serve the application for development.

	Restarts the application in a new process whenever a Python file, a view,
	or an asset changes. Each start compiles the assets again.
	"""

	name = "serve"
	no_reload: bool = option(default=False, help="serve without watching for changes")

	def __init__(self, application: Application, **values: Any):
		super().__init__(**values)
		self.application = application

	def run(self):
		base_url = self.application.container.get(helios.app.Config).base_url
		if base_url is None:
			self.fail("the application has no base URL")
		if base_url.host is None:
			self.fail(f"the base URL {base_url} has no host")
		if base_url.port is None:
			self.fail(f"the base URL {base_url} has no port")

		root = Path.cwd()
		if self.no_reload:
			self.serve(root, base_url.host, base_url.port)
		else:
			self.watch(root)

	def serve(self, root: Path, host: str, port: int):
		if self.application.container.bound(helios.assets.config.Config):
			self.compile(root)
		self.application.boot()
		# Treat SIGTERM like SIGINT. This lets Werkzeug stop serving normally
		# and lets the application clean up its resources before exiting.
		signal.signal(signal.SIGTERM, signal.default_int_handler)
		run_simple(
			host,
			port,
			self.application,
			threaded=True,
			static_files={"/": str(Path(root, "public"))},
		)

	def compile(self, root: Path):
		config = self.application.container.get(helios.assets.config.Config)
		try:
			compiled = Bundler(root).compile(
				Path(root, config.directory),
				Path(root, config.output),
				config.scripts,
				config.styles,
				minify=False,
				sourcemap=True,
			)
		except (BundlerNotFoundError, CompileError) as error:
			self.fail(str(error))
		compiled.manifest.save(Path(root, config.manifest))

	def watch(self, root: Path):
		run_process(
			root,
			target=shlex.join(self.child()),
			target_type="command",
			watch_filter=self.filter(root),
		)

	def child(self) -> list[str]:
		# The child runs the application's file again from the top, so it
		# constructs a fresh configuration and application.
		return [sys.executable, *sys.argv, "--no_reload"]

	def filter(self, root: Path) -> Filter:
		container = self.application.container
		directories = []
		if container.bound(helios.view.config.Config):
			views = container.get(helios.view.config.Config)
			directories.append(Path(root, views.directory))
		if container.bound(helios.assets.config.Config):
			assets = container.get(helios.assets.config.Config)
			directories.append(Path(root, assets.directory))
		return Filter(directories)


class Filter(DefaultFilter):
	"""Passes Python files and every file under the given directories."""

	def __init__(self, directories: list[Path]):
		super().__init__()
		self.directories = directories

	def __call__(self, change: Change, path: str) -> bool:
		if not super().__call__(change, path):
			return False

		changed = Path(path)
		if changed.suffix == ".py":
			return True
		for directory in self.directories:
			if changed.is_relative_to(directory):
				return True
		return False
