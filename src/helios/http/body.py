from dataclasses import dataclass


@dataclass
class Body:
	content: str | bytes | None = ""

	def to_bytes(self) -> bytes:
		if isinstance(self.content, bytes):
			return self.content
		return str(self.content).encode("utf8")

	def __str__(self) -> str:
		return str(self.content)
