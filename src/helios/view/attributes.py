from typing import Any

from markupsafe import Markup


class Attributes:
	def __init__(self, **values: Any):
		self.values = normalize(
			{html_name(name): value for name, value in values.items()}
		)

	@classmethod
	def from_html_names(cls, values: dict[str, Any]) -> Attributes:
		attributes = cls()
		attributes.values = normalize(values)
		return attributes

	def names(self) -> set[str]:
		return set(self.values)

	def merge(self, **defaults: Any) -> Attributes:
		merged = Attributes(**defaults).values
		for name, value in self.values.items():
			if name == "class" and name in merged:
				merged[name] = merged[name] + value
			else:
				merged[name] = value
		return Attributes.from_html_names(merged)

	def __html__(self) -> Markup:
		pairs = []
		for name, value in self.values.items():
			if name == "class":
				value = " ".join(value) or None
			if value is True:
				pairs.append(Markup.escape(name))
			elif value is not False and value is not None:
				pairs.append(Markup('{}="{}"').format(name, value))
		return Markup(" ").join(pairs)

	def __str__(self) -> str:
		return str(self.__html__())


def html_name(name: str) -> str:
	return name.removesuffix("_").replace("_", "-")


def normalize(values: dict[str, Any]) -> dict[str, Any]:
	normalized = dict(values)
	if "class" in normalized:
		normalized["class"] = classes(normalized["class"])
	return normalized


def classes(value: str | list[Any] | None) -> list[str]:
	if isinstance(value, str):
		value = [value]
	names = [name for entry in value or [] if entry for name in str(entry).split()]
	return list(dict.fromkeys(names))
