from dataclasses import dataclass
import json
from typing import Any

from helios.database import Codec, Scalar


@dataclass
class Items:
	"""A session's items, stored as a JSON object."""

	contents: dict[str, Any]


class Codec(Codec):
	converts = Items

	def encode(self, value: Items) -> Scalar:
		return json.dumps(value.contents)

	def decode(self, value: Scalar) -> Items:
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")
		contents = json.loads(value)
		if not isinstance(contents, dict):
			raise TypeError(f"expected a JSON object, got {type(contents).__name__}")
		return Items(contents)
