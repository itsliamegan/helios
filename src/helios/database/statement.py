from dataclasses import dataclass
from typing import Literal

from .clause import Clause
from .codec import Scalar

type Direction = Literal["asc", "desc"]


@dataclass
class Column:
	name: str


@dataclass
class Count:
	pass


type Expression = Column | Count


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


type Statement = Select | Insert | Update | Delete
