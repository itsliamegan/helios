from dataclasses import dataclass
from datetime import timedelta


@dataclass(init=False)
class Config:
	secure: bool
	maximum_age: timedelta

	def __init__(
		self,
		secure: bool = False,
		maximum_age: timedelta = timedelta(days=30),
	):
		if maximum_age < timedelta(0):
			raise ValueError("maximum_age cannot be negative")
		self.secure = secure
		self.maximum_age = maximum_age
