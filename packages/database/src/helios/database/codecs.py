from dataclasses import dataclass
from typing import Any, get_origin

from .codec import Codec
from .error import ModelError, qualified


@dataclass(init=False)
class Codecs:
	"""Codecs by the type that they convert.

	A lookup that finds no codec in this collection defers to the parent, if
	there is one.
	"""

	parent: Codecs | None
	converted: dict[object, Codec[Any]]

	def __init__(self, parent: Codecs | None = None):
		self.parent = parent
		self.converted = {}

	def codec(self, codec: Codec[Any]):
		registered = self.converted.get(codec.converts)
		if registered is not None:
			raise ModelError(
				f"registered codecs share the type {codec.converts.__name__}: "
				f"{qualified(type(registered))}, {qualified(type(codec))}"
			)

		self.converted[codec.converts] = codec

	def find(self, annotation: object) -> Codec[Any] | None:
		"""Return the codec for an annotation without `| None`.

		The codec is the one registered for the annotation's origin when it has
		one, or for the annotation itself otherwise.
		"""

		found = self.converted.get(get_origin(annotation) or annotation)
		if found is None and self.parent is not None:
			return self.parent.find(annotation)
		else:
			return found
