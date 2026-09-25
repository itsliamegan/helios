from dataclasses import dataclass


@dataclass(init=False)
class Errors:
	messages: dict[str, list[str]]

	def __init__(self, messages: dict[str, list[str]] | None = None):
		self.messages = {}
		for name, field_messages in (messages or {}).items():
			self.messages[name] = list(field_messages)

	def add(self, name: str, message: str):
		self.messages.setdefault(name, []).append(message)

	def first(self, name: str) -> str | None:
		if name in self.messages:
			return self.messages[name][0]
		else:
			return None

	def __getitem__(self, name: str) -> list[str]:
		return list(self.messages.get(name, []))

	def __contains__(self, name: str) -> bool:
		return name in self.messages

	def __bool__(self) -> bool:
		return bool(self.messages)
