from dataclasses import dataclass
import re
from typing import Any, Literal

from .codec import Scalar
from .condition import AnyOf

type Statement = Select | Insert | Update | Delete | Raw


@dataclass
class Select:
	table: str
	columns: tuple[ColumnExpression, ...]
	where: tuple[AnyOf, ...] = ()
	group_by: tuple[str, ...] = ()
	order_by: tuple[Order, ...] = ()
	limit: int | None = None


@dataclass
class Insert:
	table: str
	values: dict[str, Scalar | None]


@dataclass
class Update:
	table: str
	values: dict[str, Scalar | None]
	where: tuple[AnyOf, ...]


@dataclass
class Delete:
	table: str
	where: tuple[AnyOf, ...]


@dataclass
class Raw:
	sql: str
	parameters: tuple[Any, ...]

	@property
	def body(self) -> str:
		"""The SQL after its leading whitespace and comments."""

		remainder = self.sql.lstrip()
		while True:
			if remainder.startswith("--"):
				end = remainder.find("\n")
				remainder = "" if end == -1 else remainder[end + 1 :]
			elif remainder.startswith("/*"):
				end = remainder.find("*/")
				remainder = "" if end == -1 else remainder[end + 2 :]
			else:
				return remainder
			remainder = remainder.lstrip()

	@property
	def keyword(self) -> str:
		"""The body's first word in uppercase, or an empty string."""

		match = re.match(r"[A-Za-z]+", self.body)
		if match is None:
			return ""
		return match.group(0).upper()

	@property
	def summary(self) -> str:
		"""The body collapsed onto one line, shortened for error messages."""

		text = " ".join(self.body.split())
		if len(text) <= 80:
			return text
		return text[:77] + "..."


# Anything a select lists as one of its columns.
type ColumnExpression = ColumnReference | Count

type Direction = Literal["asc", "desc"]


@dataclass
class ColumnReference:
	name: str


@dataclass
class Count:
	pass


@dataclass
class Order:
	name: str
	direction: Direction
