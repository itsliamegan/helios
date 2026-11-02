from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Self

from .condition import AllOf, AnyOf, Comparison, Condition, Exists, IsNull, Membership
from .sqlite import quote_identifier
from .statement import (
	ColumnExpression,
	ColumnReference,
	Count,
	Delete,
	Insert,
	Order,
	Raw,
	Select,
	Statement,
	Update,
)


class Grammar:
	"""Compiles statements into SQL and its parameters.

	Model reads and writes become SQL only here. The store and queries build
	statements instead. A raw statement passes through unchanged.
	"""

	def compile(self, statement: Statement) -> Fragment:
		match statement:
			case Select():
				return self.select(statement)
			case Insert():
				return self.insert(statement)
			case Update():
				return self.update(statement)
			case Delete():
				return self.delete(statement)
			case Raw(sql=sql, parameters=parameters):
				return Fragment(sql, parameters)

	def select(self, statement: Select) -> Fragment:
		columns = ", ".join(
			self.column_expression(column) for column in statement.columns
		)
		return Fragment.join(
			[
				Fragment(f"SELECT {columns} FROM {quote_identifier(statement.table)}"),
				self.where(statement.where, Correlation.to(statement.table)),
				self.group_by(statement.group_by),
				self.order_by(statement.order_by),
				self.limit(statement.limit),
			]
		)

	def insert(self, statement: Insert) -> Fragment:
		columns = ", ".join(quote_identifier(name) for name in statement.values)
		placeholders = ", ".join("?" for _ in statement.values)
		return Fragment(
			f"INSERT INTO {quote_identifier(statement.table)} ({columns}) "
			f"VALUES ({placeholders})",
			tuple(statement.values.values()),
		)

	def update(self, statement: Update) -> Fragment:
		assignments = ", ".join(
			f"{quote_identifier(name)} = ?" for name in statement.values
		)
		return Fragment.join(
			[
				Fragment(
					f"UPDATE {quote_identifier(statement.table)} SET {assignments}",
					tuple(statement.values.values()),
				),
				self.where(statement.where, Correlation.to(statement.table)),
			]
		)

	def delete(self, statement: Delete) -> Fragment:
		return Fragment.join(
			[
				Fragment(f"DELETE FROM {quote_identifier(statement.table)}"),
				self.where(statement.where, Correlation.to(statement.table)),
			]
		)

	def column_expression(self, expression: ColumnExpression) -> str:
		match expression:
			case ColumnReference(name=name):
				return quote_identifier(name)
			case Count():
				return "COUNT(*)"

	def where(self, clauses: tuple[AnyOf, ...], correlation: Correlation) -> Fragment:
		if not clauses:
			return Fragment("")
		compiled = Fragment.join(
			(self.any_of(clause, correlation) for clause in clauses),
			" AND ",
		)
		return Fragment.join([Fragment(" WHERE "), compiled])

	def group_by(self, names: tuple[str, ...]) -> Fragment:
		if not names:
			return Fragment("")
		return Fragment(
			f" GROUP BY {", ".join(quote_identifier(name) for name in names)}"
		)

	def order_by(self, orders: tuple[Order, ...]) -> Fragment:
		if not orders:
			return Fragment("")
		terms = ", ".join(
			f"{quote_identifier(order.name)} {order.direction.upper()}"
			for order in orders
		)
		return Fragment(f" ORDER BY {terms}")

	def limit(self, count: int | None) -> Fragment:
		if count is None:
			return Fragment("")
		return Fragment(" LIMIT ?", (count,))

	def any_of(self, clause: AnyOf, correlation: Correlation) -> Fragment:
		groups = Fragment.join(
			(self.all_of(group, correlation) for group in clause.groups),
			" OR ",
		)
		# `IS NOT 1` also keeps rows where the clause is null, which `NOT` would
		# drop, so a negated clause matches exactly the rows the clause does not.
		negation = " IS NOT 1" if clause.negated else ""
		return Fragment.join([Fragment("("), groups, Fragment(f"){negation}")])

	def all_of(self, group: AllOf, correlation: Correlation) -> Fragment:
		conditions = Fragment.join(
			(self.condition(condition, correlation) for condition in group.conditions),
			" AND ",
		)
		return Fragment.join([Fragment("("), conditions, Fragment(")")])

	def condition(self, condition: Condition, correlation: Correlation) -> Fragment:
		match condition:
			case Comparison(name=name, comparator=comparator, value=value):
				return Fragment(f"{quote_identifier(name)} {comparator} ?", (value,))
			case IsNull(name=name):
				return Fragment(f"{quote_identifier(name)} IS NULL")
			case Membership(name=name, values=values, includes_null=includes_null):
				placeholders = ", ".join("?" for _ in values)
				sql = f"{quote_identifier(name)} IN ({placeholders})"
				if includes_null:
					sql = f"({sql} OR {quote_identifier(name)} IS NULL)"
				return Fragment(sql, values)
			case Exists():
				return self.exists(condition, correlation)

	def exists(self, condition: Exists, correlation: Correlation) -> Fragment:
		alias = quote_identifier(correlation.alias())
		inner_column = quote_identifier(condition.inner_column)
		outer_column = quote_identifier(condition.outer_column)
		return Fragment.join(
			[
				Fragment(
					f"EXISTS (SELECT 1 FROM {quote_identifier(condition.table)} "
					f"AS {alias} WHERE {alias}.{inner_column} = "
					f"{correlation.reference}.{outer_column} AND "
				),
				self.all_of(condition.group, correlation.inside(alias)),
				Fragment(")"),
			]
		)


class Correlation:
	"""The table a correlated subquery refers to at this point in a statement.

	It also hands out the aliases its subqueries take, shared across the whole
	statement.
	"""

	def __init__(self, reference: str, aliases: Aliases):
		self.reference = reference
		self.aliases = aliases

	@classmethod
	def to(cls, table: str) -> Self:
		return cls(quote_identifier(table), Aliases(table))

	def alias(self) -> str:
		return self.aliases.next()

	def inside(self, reference: str) -> Correlation:
		return Correlation(reference, self.aliases)


class Aliases:
	def __init__(self, table: str):
		self.table = table
		self.count = 0

	def next(self) -> str:
		self.count += 1
		if f"r{self.count}" == self.table:
			# This alias would shadow the outer table's name.
			self.count += 1
		return f"r{self.count}"


@dataclass
class Fragment:
	"""SQL text and its parameters, in order."""

	sql: str
	parameters: tuple[Any, ...] = ()

	@classmethod
	def join(cls, fragments: Iterable[Fragment], separator: str = "") -> Self:
		fragments = list(fragments)
		return cls(
			separator.join(fragment.sql for fragment in fragments),
			tuple(
				parameter for fragment in fragments for parameter in fragment.parameters
			),
		)
