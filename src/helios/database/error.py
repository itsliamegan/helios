from typing import TYPE_CHECKING
from uuid import UUID

from helios.http.error import NotFoundError as BaseNotFoundError

if TYPE_CHECKING:
	from .model import Model


class ModelError(TypeError):
	pass


class DatabaseError(RuntimeError):
	pass


class DatabaseBusy(DatabaseError):
	pass


class NotFoundError(BaseNotFoundError):
	def __init__(self, model_type: type[Model], id: UUID):
		self.model_type = model_type
		self.id = id
		super().__init__(f"{model_type.__name__} {id} not found")
