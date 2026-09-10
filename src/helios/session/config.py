from pathlib import Path


class Config[T = Path]:
	def __init__(self, store_file: T):
		self.store_file = store_file
