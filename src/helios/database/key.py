from dataclasses import dataclass


@dataclass
class Key:
	name: str
	operator: str

	@classmethod
	def parse(cls, text: str) -> Key | None:
		parts = text.split(" ")
		if not 1 <= len(parts) <= 2 or not all(parts):
			return None
		elif len(parts) == 1:
			return cls(parts[0], "=")
		else:
			return cls(parts[0], parts[1])
