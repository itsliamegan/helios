from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
	directory: Path
	output: Path
	scripts: list[str]
	styles: list[str]
	prefix: str = "/assets/"

	@property
	def manifest(self) -> Path:
		return Path(self.output, "manifest.json")
