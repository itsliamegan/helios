from dataclasses import dataclass

ITEM = "*"


@dataclass
class Key:
	name: str
	item: bool = False
	rest: str = ""

	@classmethod
	def parse(cls, text: str) -> Key:
		name, _, remainder = text.partition(".")
		marker, _, rest = remainder.partition(".")
		if marker == ITEM:
			return cls(name, item=True, rest=rest)
		else:
			return cls(name, rest=remainder)

	def __str__(self) -> str:
		parts = [self.name]
		if self.item:
			parts.append(ITEM)
		if self.rest:
			parts.append(self.rest)
		return ".".join(parts)
