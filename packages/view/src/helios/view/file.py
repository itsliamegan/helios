from pathlib import Path

from .source import Driver, Source


class Driver(Driver):
	"""Reads `.html` templates from a directory.

	A template is named by its path without the suffix, as in `posts/show`.
	Hidden files and folders are skipped.
	"""

	def __init__(self, directory: Path):
		self.directory = directory

	def names(self) -> list[str]:
		names = []
		for folder, _, files in self.directory.walk():
			parts = folder.relative_to(self.directory).parts
			if any(part.startswith(".") for part in parts):
				continue
			for file in files:
				path = folder.joinpath(file)
				if file.startswith(".") or path.suffix != ".html":
					continue
				names.append("/".join(parts + (path.stem,)))
		return sorted(names)

	def source(self, name: str) -> Source | None:
		path = self.locate(name)
		if path is None:
			return None
		else:
			return Source(path.read_text(), str(path))

	def locate(self, name: str) -> Path | None:
		parts = name.split("/")
		if any(part == "" or part.startswith(".") for part in parts):
			return None
		path = self.directory.joinpath(*parts[:-1], parts[-1] + ".html")
		if not path.is_file():
			return None
		else:
			return path
