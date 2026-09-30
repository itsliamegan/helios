from dataclasses import dataclass
from typing import Literal

from .condition import Clause

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


type Statement = Select
