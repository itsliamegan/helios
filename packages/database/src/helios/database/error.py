from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
	from .model import Model


class ModelError(TypeError):
	"""Raised when a model, query, or load is declared or used incorrectly."""


class DatabaseError(RuntimeError):
	"""Raised when the database fails or holds rows its models cannot read."""


class DatabaseBusyError(DatabaseError):
	pass


class ScriptError(DatabaseError):
	pass


class NotFoundError(LookupError):
	"""Raised when no row has a model's ID."""

	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")


def qualified(named: type) -> str:
	return f"{named.__module__}.{named.__qualname__}"
