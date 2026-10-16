from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from .error import BundlerNotFoundError, CompileError
from .manifest import Manifest


@dataclass
class Bundler:
	"""Compiles a project's assets using esbuild.

	esbuild must be installed in the project's node_modules.
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

		script_entries = {}
		for name in scripts:
			script_entries[Path(source, "scripts", f"{name}.js").resolve()] = name

		style_entries = {}
		for name in styles:
			style_entries[Path(source, "styles", f"{name}.css").resolve()] = name

		with TemporaryDirectory() as directory:
			metafile = Path(directory, "meta.json")

			command = [str(esbuild)]
			for entry in [*script_entries, *style_entries]:
				command.append(str(entry))
			command.extend(
				[
					"--bundle",
					"--format=esm",
					"--entry-names=[dir]/[name]-[hash]",
					f"--outbase={source}",
					f"--outdir={output}",
					f"--metafile={metafile}",
					"--log-level=error",
				]
			)
			if minify:
				command.append("--minify")
			if sourcemap:
				command.append("--sourcemap")

			result = subprocess.run(
				command,
				cwd=self.root,
				capture_output=True,
				text=True,
				check=False,
			)
			if result.returncode != 0:
				raise CompileError(result.stderr)

			outputs = json.loads(metafile.read_text())["outputs"]

		manifest = Manifest(scripts={}, styles={})
		files = []
		for key, value in outputs.items():
			# esbuild reports outputs and entry points relative to its working
			# directory, which is the root.
			file = Path(self.root, key).resolve().relative_to(output.resolve())
			files.append(file)

			if "entryPoint" in value:
				entry = Path(self.root, value["entryPoint"]).resolve()

				# esbuild writes a script's imported stylesheets to a file of
				# their own, so the script no longer compiles to one file.
				if "cssBundle" in value:
					raise CompileError(f"script imports a stylesheet: {entry}")

				if entry in script_entries:
					manifest.scripts[script_entries[entry]] = file.as_posix()
				else:
					manifest.styles[style_entries[entry]] = file.as_posix()

		return Compiled(manifest=manifest, files=sorted(files))


@dataclass
class Compiled:
	"""A compile's manifest and the files it wrote.

	The files are relative to the output directory.
	"""

	manifest: Manifest
	files: list[Path]
