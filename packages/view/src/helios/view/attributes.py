from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Self

from luna import inflect
from markupsafe import Markup

GLOBAL_ATTRIBUTES = {"class", "id", "hidden"}


@dataclass(init=False, eq=False)
class Attributes:
	"""A bag of HTML attributes.

	Names provided to the constructor should use underscores, e.g.
	`data_controller`. Names will be rendered as HTML using dashes, e.g.
	`data-controller`.

	Boolean attribute values are converted to a present or absent attribute, so
	setting an attribute to `True` will render its name whereas setting it to
	`False` or `None` will omit it entirely.

	The `class` attribute can hold a list of class names that will be joined
	together when rendered as HTML.
	"""

	values: dict[str, Any]

	def __init__(self, **values: Any):
		self.values = split_class_names(
			{html_name(name): value for name, value in values.items()}
		)

	@classmethod
	def from_html_names(cls, values: Mapping[str, Any]) -> Self:
		attributes = cls()
		attributes.values = split_class_names(values)
		return attributes

	@classmethod
	def is_global(cls, name: str) -> bool:
		return name in GLOBAL_ATTRIBUTES or name.startswith("data-")

	def names(self) -> set[str]:
		return set(self.values)

	def merge(self, **defaults: Any) -> Attributes:
		"""Return a new set of attributes using the defaults provided.

		An existing value for the `class` attribute will be combined with a
		provided one. Otherwise an existing value will overwrite a provided one.
		"""

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
	return inflect.dash(name)


def split_class_names(values: Mapping[str, Any]) -> dict[str, Any]:
	split = dict(values)
	if "class" in split:
		split["class"] = class_names(split["class"])
	return split


def class_names(value: str | Sequence[Any] | None) -> list[str]:
	if not value:
		value = []
	if isinstance(value, str):
		value = [value]
	names = []
	for entry in value:
		if entry:
			names.extend(str(entry).split())
	return list(dict.fromkeys(names))
