from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
	"""Where an application's assets are and what they compile to.

	The directories are relative to the application's root. The prefix is the
	URL path the output directory is served at, and ends in a slash.
	"""

	directory: Path
	output: Path
	scripts: list[str]
	styles: list[str]
	prefix: str = "/assets/"

	@property
	def manifest(self) -> Path:
		return Path(self.output, "manifest.json")
