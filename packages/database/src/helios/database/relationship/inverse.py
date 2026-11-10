from typing import TYPE_CHECKING
import uuid

from ..error import ModelError
from .relationship import Relationship

if TYPE_CHECKING:
	from ..model import Model


class Inverse(Relationship):
	@property
	def owner_column(self) -> str:
		return "id"

	@property
	def target_column(self) -> str:
		return self.id_name

	def check_target(self, target_type: type[Model]):
		column = target_type.columns.get(self.id_name)
		if column is None or column.annotation is not uuid.UUID:
			raise ModelError(
				f"{self.label}: {target_type.__name__}.{self.id_name} "
				"does not hold a UUID"
			)
