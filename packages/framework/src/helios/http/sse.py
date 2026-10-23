from collections.abc import Generator, Iterable
from dataclasses import dataclass
import re


@dataclass
class Events:
	items: Iterable[Event | Comment]

	def encode(self) -> Generator[bytes]:
		try:
			for item in self.items:
				yield item.encode()
		finally:
			# A generator's own cleanup runs only if it is closed, which the
			# server does when the client disconnects or the stream ends.
			if isinstance(self.items, Generator):
				self.items.close()


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
		# A Markup value escapes any text combined with it, so the lines are
		# split from a plain string.
		data = str(self.data)
		for line in re.split(r"\r\n|\r|\n", data):
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
