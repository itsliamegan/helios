from collections.abc import Collection
from typing import Any

MISSING: Any = object()


class DeclarationError(Exception):
	def __init__(self, name: str, detail: str):
		super().__init__(f"{name}: {detail}")
		self.name = name
		self.detail = detail


def check_keywords(
	owner: type,
	noun: str,
	given: Collection[str],
	accepted: Collection[str],
	required: Collection[str],
):
	unexpected = [name for name in given if name not in accepted]
	if unexpected:
		raise TypeError(
			f"{owner.__name__} got unexpected {noun}: {", ".join(unexpected)}"
		)

	missing = [name for name in required if name not in given]
	if missing:
		raise TypeError(f"{owner.__name__} is missing {noun}: {", ".join(missing)}")
