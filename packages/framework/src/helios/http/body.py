from collections.abc import Iterable
from dataclasses import dataclass

type Body = Buffered | Stream


@dataclass
class Buffered:
	content: str | bytes = ""

	def to_bytes(self) -> bytes:
		if isinstance(self.content, bytes):
			return self.content
		return str(self.content).encode("utf8")

	def __str__(self) -> str:
		return str(self.content)


@dataclass
class Stream:
	chunks: Iterable[bytes]


def body(content: str | bytes = "") -> Buffered:
	return Buffered(content)
