from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Source:
	text: str
	path: str | None
	version: int


class Driver(ABC):
	@abstractmethod
	def names(self) -> list[str]: ...

	@abstractmethod
	def source(self, name: str) -> Source | None: ...
