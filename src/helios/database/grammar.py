from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .condition import Clause, Comparison, Condition, Group, IsNull, Membership
from .sqlite import quote_identifier
from .statement import Column, Count, Direction, Expression, Select, Statement


@dataclass
class Fragment:
	sql: str
	parameters: tuple[Any, ...] = ()

	@classmethod
	def join(cls, fragments: Iterable[Fragment], separator: str = "") -> Fragment:
		fragments = list(fragments)
		return cls(
			separator.join(fragment.sql for fragment in fragments),
			tuple(
				parameter for fragment in fragments for parameter in fragment.parameters
			),
		)


class Grammar:
	def compile(self, statement: Statement) -> Fragment:
		match statement:
			case Select():
				return self.select(statement)

	def select(self, statement: Select) -> Fragment:
		columns = ", ".join(self.expression(column) for column in statement.columns)
		return Fragment.join(
			[
				Fragment(f"SELECT {columns} FROM {quote_identifier(statement.table)}"),
				self.where(statement.where),
				self.group_by(statement.group_by),
				self.order(statement.ordering),
				self.limit(statement.limit),
			]
		)

	def expression(self, expression: Expression) -> str:
		match expression:
			case Column(name=name):
				return quote_identifier(name)
			case Count():
				return "COUNT(*)"

	def where(self, clauses: tuple[Clause, ...]) -> Fragment:
		if not clauses:
			return Fragment("")
		compiled = Fragment.join((self.clause(clause) for clause in clauses), " AND ")
		return Fragment.join([Fragment(" WHERE "), compiled])

	def clause(self, clause: Clause) -> Fragment:
		groups = Fragment.join((self.group(group) for group in clause.groups), " OR ")
		negation = " IS NOT 1" if clause.negated else ""
		return Fragment.join([Fragment("("), groups, Fragment(f"){negation}")])

	def group(self, group: Group) -> Fragment:
		conditions = Fragment.join(
			(self.condition(condition) for condition in group.conditions),
			" AND ",
		)
		return Fragment.join([Fragment("("), conditions, Fragment(")")])

	def condition(self, condition: Condition) -> Fragment:
		match condition:
			case Comparison(name=name, operator=operator, value=value):
				return Fragment(f"{quote_identifier(name)} {operator} ?", (value,))
			case IsNull(name=name):
				return Fragment(f"{quote_identifier(name)} IS NULL")
			case Membership(name=name, values=values, includes_null=includes_null):
				placeholders = ", ".join("?" for _ in values)
				sql = f"{quote_identifier(name)} IN ({placeholders})"
				if includes_null:
					sql = f"({sql} OR {quote_identifier(name)} IS NULL)"
				return Fragment(sql, values)

	def group_by(self, names: tuple[str, ...]) -> Fragment:
		if not names:
			return Fragment("")
		return Fragment(
			f" GROUP BY {", ".join(quote_identifier(name) for name in names)}"
		)

	def order(self, ordering: tuple[tuple[str, Direction], ...]) -> Fragment:
		if not ordering:
			return Fragment("")
		keys = ", ".join(
			f"{quote_identifier(name)} {direction.upper()}"
			for name, direction in ordering
		)
		return Fragment(f" ORDER BY {keys}")

	def limit(self, count: int | None) -> Fragment:
		if count is None:
			return Fragment("")
		return Fragment(" LIMIT ?", (count,))
