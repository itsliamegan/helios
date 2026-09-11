from pathlib import Path


class Config:
	def __init__(self, store_file: Path, secure: bool = False):
		self.store_file = store_file
		self.secure = secure
