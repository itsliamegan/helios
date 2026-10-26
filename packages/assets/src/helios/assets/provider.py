from helios.app import Application, Container, Provider

from .assets import Assets
from .config import Config
from .error import ManifestNotFoundError
from .manifest import Manifest


class Provider(Provider):
	"""Provides `Assets` from the compiled manifest.

	The manifest is read while booting, so an application whose assets are not
	compiled fails to start.
	"""

	def __init__(self, config: Config):
		self.config = config

	def register(self, container: Container):
		container.instance(Config, self.config)
		container.singleton(Assets, self.assets)

	def boot(self, application: Application):
		application.container.get(Assets)

	def assets(self, container: Container) -> Assets:
		try:
			manifest = Manifest.load(self.config.manifest)
		except FileNotFoundError:
			raise ManifestNotFoundError(
				f"manifest not found, so the assets are not compiled: {self.config.manifest}"
			) from None
		return Assets(manifest, self.config.prefix)
