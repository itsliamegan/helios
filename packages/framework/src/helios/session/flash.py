from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(init=False)
class Flashes:
	flashes: dict[str, Flash]

	def __init__(self, flashes: Mapping[str, Any] | None = None):
		flashes = flashes or {}
		self.flashes = {}
		for name in flashes:
			self.flashes[name] = Flash(name, flashes[name])

	def dirty(self) -> dict[str, Any]:
		dirty = {}
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				dirty[name] = self.flashes[name].value
		return dirty

	def is_dirty(self) -> bool:
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				return True
		return False

	def __getitem__(self, name: str) -> Any:
		return self.flashes[name].value

	def get(self, name: str, default: Any = None) -> Any:
		if name in self.flashes:
			return self.flashes[name].value
		else:
			return default

	def __setitem__(self, name: str, value: Any):
		self.flashes[name] = Flash(name, value, is_dirty=True)

	def __contains__(self, name: object) -> bool:
		return name in self.flashes


@dataclass
class Flash:
	name: str
	value: Any
	is_dirty: bool = False
