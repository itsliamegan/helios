from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Source:
	"""A template's text and the path it was read from, if any."""

	text: str
	path: str | None


class Driver(ABC):
	"""Finds template sources by name."""

	@abstractmethod
	def names(self) -> list[str]: ...

	@abstractmethod
	def source(self, name: str) -> Source | None: ...
