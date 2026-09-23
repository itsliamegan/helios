from .source import Source


class Driver:
	def __init__(self, templates: dict[str, str]):
		self.templates = templates

	def names(self) -> list[str]:
		return sorted(self.templates)

	def source(self, name: str) -> Source | None:
		if name not in self.templates:
			return None
		else:
			return Source(self.templates[name], None, 0)

	def is_current(self, name: str, source: Source) -> bool:
		return self.templates.get(name) == source.text
