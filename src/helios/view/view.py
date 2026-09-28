from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class View:
	name: str
	shared: dict[str, Any]

	def __init__(self, name: str, shared: dict[str, Any] | None = None):
		self.name = name
		self.shared = shared or {}

	def share(self, name: str, value: Any):
		self.shared[name] = value
