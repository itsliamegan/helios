from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
	directory: Path
