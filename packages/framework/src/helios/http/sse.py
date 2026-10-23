from collections.abc import Generator, Iterable
from dataclasses import dataclass
import re


@dataclass(init=False)
class Event:
	data: str
	event: str | None
	id: str | None

	def __init__(self, data: str, event: str | None = None, id: str | None = None):
		if event is not None and ("\r" in event or "\n" in event):
			raise ValueError("event types must not contain newline characters")
		if id is not None and ("\r" in id or "\n" in id or "\0" in id):
			raise ValueError("event IDs must not contain newline or null characters")

		self.data = data
		self.event = event
		self.id = id

	def encode(self) -> bytes:
		lines = []
		if self.event is not None:
			lines.append(f"event: {self.event}")
		# Markup escapes text it is combined with, so convert data to a plain
		# string first.
		for line in re.split(r"\r\n|\r|\n", str(self.data)):
			lines.append(f"data: {line}")
		if self.id is not None:
			lines.append(f"id: {self.id}")
		lines.append("")
		lines.append("")
		return "\n".join(lines).encode()


@dataclass(init=False)
class Comment:
	text: str

	def __init__(self, text: str):
		if "\r" in text or "\n" in text:
			raise ValueError("comments must not contain newline characters")

		self.text = text

	def encode(self) -> bytes:
		return f": {self.text}\n\n".encode()


def encode(items: Iterable[Event | Comment]) -> Generator[bytes]:
	"""Encode each event or comment in turn.

	Closing the encoded stream closes `items` when it is a generator, so that
	the generator's own cleanup runs when the client disconnects.
	"""
	try:
		for item in items:
			yield item.encode()
	finally:
		if isinstance(items, Generator):
			items.close()
