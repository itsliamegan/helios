from pathlib import Path


class Config:
	def __init__(self, store_file: Path):
		self.store_file = store_file
