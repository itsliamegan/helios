from dataclasses import dataclass

ITEM = "*"


@dataclass(frozen=True)
class Key:
	name: str
	item: bool = False
	rest: str = ""

	@classmethod
	def parse(cls, text: str) -> Key:
		name, _, remainder = text.partition(".")
		marker, _, rest = remainder.partition(".")
		if marker == ITEM:
			return cls(name, True, rest)
		else:
			return cls(name, False, remainder)

	def __str__(self) -> str:
		parts = [self.name]
		if self.item:
			parts.append(ITEM)
		if self.rest:
			parts.append(self.rest)
		return ".".join(parts)
