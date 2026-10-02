from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .codec import Scalar, encode
from .column import Column


@dataclass
class Clause:
	groups: tuple[Group, ...]
	negated: bool = False


@dataclass
class Group:
	conditions: tuple[Condition, ...]


type Condition = Comparison | IsNull | Membership | Exists


@dataclass
class Comparison:
	name: str
	operator: Operator
	value: Scalar

	@classmethod
	def parse(cls, column: Column, operator: Operator, value: object) -> Comparison:
		if value is None:
			raise ValueError("cannot compare with None")

		column.check(value)
		return cls(column.name, operator, encode(column.codec, value))


@dataclass
class IsNull:
	name: str

	@classmethod
	def parse(cls, column: Column) -> IsNull:
		column.check(None)
		return cls(column.name)


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool

	@classmethod
	def parse(cls, column: Column, value: object) -> Membership:
		if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
			raise TypeError(
				"expected an iterable other than str or bytes, "
				f"got {type(value).__name__}"
			)

		members = list(value)
		for member in members:
			column.check(member)
		values = tuple(
			dict.fromkeys(
				encode(column.codec, member) for member in members if member is not None
			)
		)
		return cls(column.name, values, None in members)


@dataclass
class Exists:
	table: str
	column: str
	outer_column: str
	group: Group


type Operator = Literal["=", "<", "<=", ">", ">="]
