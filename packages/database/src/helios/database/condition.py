from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Self

from .codec import Scalar, encode
from .column import Column


@dataclass
class AnyOf:
	"""Matches a row that meets at least one group.

	Negated, it matches exactly the rows it otherwise would not. A statement's
	clauses are each an `AnyOf`, and a row must meet all of them.
	"""

	groups: tuple[AllOf, ...]
	negated: bool = False


@dataclass
class AllOf:
	"""Matches a row that meets every condition."""

	conditions: tuple[Condition, ...]


type Condition = Comparison | IsNull | Membership | Exists


@dataclass
class Comparison:
	name: str
	comparator: Comparator
	value: Scalar

	@classmethod
	def parse(cls, column: Column, comparator: Comparator, value: object) -> Self:
		if value is None:
			raise ValueError("cannot compare with None")

		column.check(value)
		return cls(column.name, comparator, encode(column.codec, value))


@dataclass
class IsNull:
	name: str

	@classmethod
	def parse(cls, column: Column) -> Self:
		column.check(None)
		return cls(column.name)


@dataclass
class Membership:
	name: str
	values: tuple[Scalar, ...]
	includes_null: bool

	@classmethod
	def parse(cls, column: Column, value: object) -> Self:
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
	"""Matches a related row that meets `group`.

	The related row is in `table`, and its `inner_column` equals the outer
	row's `outer_column`.
	"""

	table: str
	inner_column: str
	outer_column: str
	group: AllOf


type Comparator = Literal["=", "<", "<=", ">", ">="]
