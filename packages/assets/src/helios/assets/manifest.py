from dataclasses import dataclass
import json
from pathlib import Path
from typing import Self


@dataclass
class Manifest:
	"""Records each asset's entry name mapped to its compiled file name.

	Bucketed by asset type.
	"""

	scripts: dict[str, str]
	styles: dict[str, str]

	@classmethod
	def load(cls, path: Path) -> Self:
		value = json.loads(path.read_text())
		return cls(value["scripts"], value["styles"])

	def save(self, path: Path):
		value = {"scripts": self.scripts, "styles": self.styles}
		path.write_text(json.dumps(value, indent="\t") + "\n")
