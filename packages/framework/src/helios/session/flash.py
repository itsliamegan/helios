from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class Flash:
	"""A set of items kept only for the next request and cleared afterwards.

	Setting an item marks it as dirty. Only dirty items reach the next request.
	"""

	items: dict[str, Any]
	_dirty: set[str]

	def __init__(self, items: Mapping[str, Any] | None = None):
		self.items = dict(items or {})
		self._dirty = set()
		self.closed = False

	def dirty(self) -> dict[str, Any]:
		dirty = {}
		for name in self._dirty:
			dirty[name] = self.items[name]
		return dirty

	def is_dirty(self) -> bool:
		return len(self._dirty) > 0

	def __getitem__(self, name: str) -> Any:
		return self.items[name]

	def get(self, name: str, default: Any = None) -> Any:
		if name in self.items:
			return self.items[name]
		else:
			return default

	def __setitem__(self, name: str, value: Any):
		if self.closed:
			raise RuntimeError("the flash is closed")

		self.items[name] = value
		self._dirty.add(name)

	def __contains__(self, name: object) -> bool:
		return name in self.items

	def close(self):
		self.closed = True
