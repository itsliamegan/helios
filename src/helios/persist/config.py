from pathlib import Path


class Config[T = Path]:
	def __init__(self, lock_file: T):
		self.lock_file = lock_file
