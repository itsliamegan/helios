from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class View:
	"""A named template and the values shared with it before it renders."""

	name: str
	shared: dict[str, Any]

	def __init__(self, name: str, shared: Mapping[str, Any] | None = None):
		self.name = name
		self.shared = dict(shared or {})

	def share(self, name: str, value: Any):
		self.shared[name] = value
