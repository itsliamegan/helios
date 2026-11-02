from dataclasses import dataclass
from datetime import timedelta

from . import database, memory


@dataclass(init=False)
class Config:
	driver: database.Config | memory.Config
	secure: bool
	maximum_age: timedelta

	def __init__(
		self,
		driver: database.Config | memory.Config,
		secure: bool = False,
		maximum_age: timedelta = timedelta(days=30),
	):
		if maximum_age < timedelta(0):
			raise ValueError("maximum_age cannot be negative")
		self.driver = driver
		self.secure = secure
		self.maximum_age = maximum_age
