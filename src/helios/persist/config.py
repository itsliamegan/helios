from pathlib import Path


class Config:
	def __init__(self, lock_file: Path):
		self.lock_file = lock_file
