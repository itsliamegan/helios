from dataclasses import dataclass
from typing import Literal

from .codec import Scalar

type Operator = Literal["=", "<", "<=", ">", ">="]


@dataclass
class Comparison:
	name: str
	operator: Operator
	value: Scalar


@dataclass
class IsNull:
	name: str


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool


type Condition = Comparison | IsNull | Membership
