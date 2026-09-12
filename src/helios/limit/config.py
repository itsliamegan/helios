from datetime import timedelta


class Config:
	def __init__(self, header: str, limit: int, window: timedelta):
		self.header = header
		self.limit = limit
		self.window = window
