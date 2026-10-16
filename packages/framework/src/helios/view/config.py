from pathlib import Path


class Config:
	def __init__(self, directory: Path, reload: bool = False):
		self.directory = directory
		self.reload = reload
