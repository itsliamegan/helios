from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Self

from .clause import Clause, Comparison, Condition, Exists, Group, IsNull, Membership
from .sqlite import quote_identifier
from .statement import (
	ColumnReference,
	Count,
	Delete,
	Direction,
	Expression,
	Insert,
	Raw,
	Select,
	Statement,
	Update,
)


class Grammar:
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
		columns = ", ".join(self.expression(column) for column in statement.columns)
		return Fragment.join(
			[
				Fragment(f"SELECT {columns} FROM {quote_identifier(statement.table)}"),
				self.where(statement.where, Scope.of(statement.table)),
				self.group_by(statement.group_by),
				self.order(statement.ordering),
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
				self.where(statement.where, Scope.of(statement.table)),
			]
		)

	def delete(self, statement: Delete) -> Fragment:
		return Fragment.join(
			[
				Fragment(f"DELETE FROM {quote_identifier(statement.table)}"),
				self.where(statement.where, Scope.of(statement.table)),
			]
		)

	def expression(self, expression: Expression) -> str:
		match expression:
			case ColumnReference(name=name):
				return quote_identifier(name)
			case Count():
				return "COUNT(*)"

	def where(self, clauses: tuple[Clause, ...], scope: Scope) -> Fragment:
		if not clauses:
			return Fragment("")
		compiled = Fragment.join(
			(self.clause(clause, scope) for clause in clauses),
			" AND ",
		)
		return Fragment.join([Fragment(" WHERE "), compiled])

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

	def clause(self, clause: Clause, scope: Scope) -> Fragment:
		groups = Fragment.join(
			(self.group(group, scope) for group in clause.groups),
			" OR ",
		)
		negation = " IS NOT 1" if clause.negated else ""
		return Fragment.join([Fragment("("), groups, Fragment(f"){negation}")])

	def group(self, group: Group, scope: Scope) -> Fragment:
		conditions = Fragment.join(
			(self.condition(condition, scope) for condition in group.conditions),
			" AND ",
		)
		return Fragment.join([Fragment("("), conditions, Fragment(")")])

	def condition(self, condition: Condition, scope: Scope) -> Fragment:
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
			case Exists():
				return self.exists(condition, scope)

	def exists(self, condition: Exists, scope: Scope) -> Fragment:
		alias = quote_identifier(scope.alias())
		column = quote_identifier(condition.column)
		outer_column = quote_identifier(condition.outer_column)
		return Fragment.join(
			[
				Fragment(
					f"EXISTS (SELECT 1 FROM {quote_identifier(condition.table)} "
					f"AS {alias} WHERE {alias}.{column} = "
					f"{scope.reference}.{outer_column} AND "
				),
				self.group(condition.group, scope.inside(alias)),
				Fragment(")"),
			]
		)


class Scope:
	def __init__(self, reference: str, aliases: Aliases):
		self.reference = reference
		self.aliases = aliases

	@classmethod
	def of(cls, table: str) -> Self:
		return cls(quote_identifier(table), Aliases(table))

	def alias(self) -> str:
		return self.aliases.next()

	def inside(self, reference: str) -> Scope:
		return Scope(reference, self.aliases)


class Aliases:
	def __init__(self, table: str):
		self.table = table
		self.count = 0

	def next(self) -> str:
		self.count += 1
		if f"r{self.count}" == self.table:
			self.count += 1
		return f"r{self.count}"


@dataclass
class Fragment:
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
