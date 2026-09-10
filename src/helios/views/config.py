from pathlib import Path


class Config[T = Path]:
	def __init__(self, dir: T):
		self.dir = dir
