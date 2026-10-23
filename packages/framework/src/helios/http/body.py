from collections.abc import Iterable
from dataclasses import dataclass

type Body = Buffered | Stream


@dataclass
class Buffered:
	"""A body held in memory."""

	content: str | bytes = ""

	def to_bytes(self) -> bytes:
		if isinstance(self.content, bytes):
			return self.content
		return str(self.content).encode("utf8")

	def __str__(self) -> str:
		return str(self.content)


@dataclass
class Stream:
	"""A body sent in chunks as it is produced."""

	chunks: Iterable[bytes]
