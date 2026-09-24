from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

GLOBAL_ATTRIBUTES = {"class", "id", "hidden"}


@dataclass(init=False, eq=False)
class Attributes:
	values: dict[str, Any]

	def __init__(self, **values: Any):
		self.values = split_class_names(
			{html_name(name): value for name, value in values.items()}
		)

	@classmethod
	def from_html_names(cls, values: dict[str, Any]) -> Attributes:
		attributes = cls()
		attributes.values = split_class_names(values)
		return attributes

	@classmethod
	def is_global(cls, name: str) -> bool:
		return name in GLOBAL_ATTRIBUTES or name.startswith("data-")

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


def split_class_names(values: dict[str, Any]) -> dict[str, Any]:
	split = dict(values)
	if "class" in split:
		split["class"] = class_names(split["class"])
	return split


def class_names(value: str | list[Any] | None) -> list[str]:
	if not value:
		value = []
	if isinstance(value, str):
		value = [value]
	names = []
	for entry in value:
		if entry:
			names.extend(str(entry).split())
	return list(dict.fromkeys(names))
