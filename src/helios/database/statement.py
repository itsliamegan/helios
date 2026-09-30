from dataclasses import dataclass
from typing import Any, Literal

from .clause import Clause
from .codec import Scalar

type Statement = Select | Insert | Update | Delete | Raw


@dataclass
class Select:
	table: str
	columns: tuple[Expression, ...]
	where: tuple[Clause, ...] = ()
	group_by: tuple[str, ...] = ()
	ordering: tuple[tuple[str, Direction], ...] = ()
	limit: int | None = None


@dataclass
class Insert:
	table: str
	values: dict[str, Scalar | None]


@dataclass
class Update:
	table: str
	values: dict[str, Scalar | None]
	where: tuple[Clause, ...]


@dataclass
class Delete:
	table: str
	where: tuple[Clause, ...]


@dataclass
class Raw:
	sql: str
	parameters: tuple[Any, ...]


type Expression = Column | Count

type Direction = Literal["asc", "desc"]


@dataclass
class Column:
	name: str


@dataclass
class Count:
	pass
