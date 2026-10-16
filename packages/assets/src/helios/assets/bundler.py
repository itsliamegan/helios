from dataclasses import dataclass
from pathlib import Path
import shutil

from .error import BundlerNotFoundError
from .manifest import Manifest


@dataclass
class Bundler:
	"""Compiles a project's scripts and styles with the esbuild installed in
	its root's node_modules.
	"""

	root: Path

	def compile(
		self,
		source: Path,
		output: Path,
		scripts: list[str],
		styles: list[str],
		*,
		minify: bool,
		sourcemap: bool,
	) -> Compiled:
		if output.exists():
			shutil.rmtree(output)
		output.mkdir(parents=True)

		if not scripts and not styles:
			return Compiled(manifest=Manifest(scripts={}, styles={}), files=[])

		esbuild = Path(self.root, "node_modules", ".bin", "esbuild")
		if not esbuild.exists():
			raise BundlerNotFoundError(f"esbuild not found: {esbuild}")

		raise NotImplementedError


@dataclass
class Compiled:
	"""A compile's manifest and the files it wrote, relative to its output
	directory.
	"""

	manifest: Manifest
	files: list[Path]
