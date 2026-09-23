from pathlib import Path


class Config:
	def __init__(self, dir: Path, reload: bool = False):
		self.dir = dir
		self.reload = reload
