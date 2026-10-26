from typing import TYPE_CHECKING
from uuid import UUID

from helios.http.error import NotFoundError as BaseNotFoundError

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


class NotFoundError(BaseNotFoundError):
	"""Raised when no row has a model's ID. Left uncaught, it renders as a 404."""

	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")
