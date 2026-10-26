from dataclasses import dataclass
from datetime import timedelta


@dataclass
class Config:
	header: str
	limit: int
	window: timedelta
