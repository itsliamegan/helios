from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path


@dataclass
class Config:
	path: Path
	migrations: Path = Path("database", "migrations")
	busy_timeout: timedelta = timedelta(seconds=30)
