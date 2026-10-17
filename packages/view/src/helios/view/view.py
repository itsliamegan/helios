from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class View:
	name: str
	shared: dict[str, Any]

	def __init__(self, name: str, shared: Mapping[str, Any] | None = None):
		shared = shared or {}
		self.name = name
		self.shared = dict(shared)

	def share(self, name: str, value: Any):
		self.shared[name] = value
