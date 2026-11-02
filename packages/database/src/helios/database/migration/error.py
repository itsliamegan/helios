from helios.database.error import DatabaseError


class MigrationError(DatabaseError):
	pass


class ForeignKeyError(MigrationError):
	"""A migration left rows that reference missing parents.

	Each violation is a `PRAGMA foreign_key_check` row: the child table, the
	child row's rowid, the parent table, and the foreign key's index.
	"""

	def __init__(self, message: str, violations: list[tuple]):
		super().__init__(message)
		self.violations = violations
