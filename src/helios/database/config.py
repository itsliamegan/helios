from datetime import timedelta
from pathlib import Path


class Config:
	def __init__(
		self,
		database_file: Path,
		busy_timeout: timedelta = timedelta(seconds=30),
	):
		if not isinstance(database_file, Path):
			raise TypeError("database_file must be a Path")
		if not isinstance(busy_timeout, timedelta):
			raise TypeError("busy_timeout must be a timedelta")
		milliseconds = busy_timeout // timedelta(milliseconds=1)
		if milliseconds < 0:
			raise ValueError("busy_timeout cannot be negative")
		if milliseconds > 2_147_483_647:
			raise ValueError("busy_timeout is too large")
		self.database_file = database_file
		self.busy_timeout = busy_timeout
		self.busy_timeout_milliseconds = milliseconds
