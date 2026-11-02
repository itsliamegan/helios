from dataclasses import dataclass
from datetime import timedelta

from . import database, memory


@dataclass(init=False)
class Config:
	secure: bool
	maximum_age: timedelta
	driver: database.Config | memory.Config

	def __init__(
		self,
		secure: bool = False,
		maximum_age: timedelta = timedelta(days=30),
		driver: database.Config | memory.Config | None = None,
	):
		if maximum_age < timedelta(0):
			raise ValueError("maximum_age cannot be negative")
		self.secure = secure
		self.maximum_age = maximum_age
		self.driver = driver or database.Config()
