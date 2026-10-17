from pathlib import Path
from typing import Any

from luna.cli import Command

from helios.app import Application

from .bundler import Bundler
from .config import Config
from .error import BundlerNotFoundError, CompileError


class Compile(Command):
	"""Compile the application's assets for a deploy."""

	name = "assets:compile"

	def __init__(self, application: Application, **values: Any):
		super().__init__(**values)
		self.application = application

	def run(self):
		container = self.application.container
		if not container.bound(Config):
			self.fail("the application has no assets configuration")
		config = container.get(Config)

		root = Path.cwd()
		try:
			compiled = Bundler(root).compile(
				Path(root, config.directory),
				Path(root, config.output),
				config.scripts,
				config.styles,
				minify=True,
				sourcemap=False,
			)
		except (BundlerNotFoundError, CompileError) as error:
			self.fail(str(error))
		compiled.manifest.save(Path(root, config.manifest))
