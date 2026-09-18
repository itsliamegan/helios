from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass
class Config:
	database_file: Path
	busy_timeout: timedelta = timedelta(seconds=30)
