from pathlib import Path


class Config[T = Path]:
	def __init__(self, store_file: T, *, secure: bool = False):
		self.store_file = store_file
		self.secure = secure
