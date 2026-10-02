from typing import Any


class State:
	def __init__(self, values: dict[str, Any], *, stored: bool):
		self.values = values
		self.loaded: dict[str, object] = {}
		self.stored = stored
