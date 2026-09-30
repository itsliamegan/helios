from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .condition import Clause, Comparison, Condition, Group, IsNull, Membership
from .query import Query
from .sqlite import quote_identifier


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
	def select(self, query: Query[Any], count: int | None) -> Fragment:
		columns = ", ".join(
			quote_identifier(name) for name in query.model_type.attributes
		)
		return Fragment.join(
			[
				Fragment(f"SELECT {columns} FROM {self.table(query)}"),
				self.where(query),
				self.order(query),
				self.limit(count),
			]
		)

	def count_by(self, query: Query[Any], name: str) -> Fragment:
		column = quote_identifier(name)
		return Fragment.join(
			[
				Fragment(f"SELECT {column}, COUNT(*) FROM {self.table(query)}"),
				self.where(query),
				Fragment(f" GROUP BY {column}"),
			]
		)

	def exists(self, query: Query[Any]) -> Fragment:
		return Fragment.join(
			[
				Fragment(f"SELECT EXISTS (SELECT 1 FROM {self.table(query)}"),
				self.where(query),
				self.limit(query.count),
				Fragment(")"),
			]
		)

	def table(self, query: Query[Any]) -> str:
		return quote_identifier(query.model_type.table)

	def where(self, query: Query[Any]) -> Fragment:
		if not query.clauses:
			return Fragment("")
		clauses = Fragment.join(
			(self.clause(clause) for clause in query.clauses), " AND "
		)
		return Fragment.join([Fragment(" WHERE "), clauses])

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

	def order(self, query: Query[Any]) -> Fragment:
		if not query.ordering:
			return Fragment("")
		keys = ", ".join(
			f"{quote_identifier(name)} {direction.upper()}"
			for name, direction in query.ordering
		)
		return Fragment(f" ORDER BY {keys}")

	def limit(self, count: int | None) -> Fragment:
		if count is None:
			return Fragment("")
		return Fragment(" LIMIT ?", (count,))
