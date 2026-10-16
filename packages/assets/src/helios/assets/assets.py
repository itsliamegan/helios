from dataclasses import dataclass

from markupsafe import Markup

from .error import EntryNotFoundError
from .manifest import Manifest


@dataclass
class Assets:
	"""A generator for tags used to include assets by their compiled path. Paths
	are prefixed with a constant URL prefix that ends in a slash.
	"""

	manifest: Manifest
	prefix: str

	def script(self, name: str) -> Markup:
		if name not in self.manifest.scripts:
			raise EntryNotFoundError(f"script not found: {name}")

		src = self.prefix + self.manifest.scripts[name]
		return Markup('<script type="module" src="{}"></script>').format(src)

	def style(self, name: str) -> Markup:
		if name not in self.manifest.styles:
			raise EntryNotFoundError(f"style not found: {name}")

		href = self.prefix + self.manifest.styles[name]
		return Markup('<link rel="stylesheet" href="{}">').format(href)
