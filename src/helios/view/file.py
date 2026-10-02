from pathlib import Path

from .source import Driver, Source


class Driver(Driver):
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
				names.append(".".join(parts + (path.stem,)))
		return sorted(names)

	def source(self, name: str) -> Source | None:
		path = self.locate(name)
		if path is None:
			return None
		else:
			version = path.stat().st_mtime_ns
			return Source(path.read_text(), str(path), version)

	def is_current(self, name: str, source: Source) -> bool:
		path = self.locate(name)
		if path is None:
			return False
		else:
			return path.stat().st_mtime_ns == source.version

	def locate(self, name: str) -> Path | None:
		parts = name.split(".")
		if any(part == "" or part.startswith(".") for part in parts):
			return None
		path = self.directory.joinpath(*parts).with_suffix(".html")
		if not path.is_file():
			return None
		else:
			return path
