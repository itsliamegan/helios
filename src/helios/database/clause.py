from dataclasses import dataclass

from .condition import Condition

type Group = tuple[Condition, ...]


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False
