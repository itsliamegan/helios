from dataclasses import dataclass
from typing import Protocol


@dataclass
class Source:
	text: str
	path: str | None
	version: int


class Driver(Protocol):
	def names(self) -> list[str]: ...

	def source(self, name: str) -> Source | None: ...

	def is_current(self, name: str, source: Source) -> bool: ...
