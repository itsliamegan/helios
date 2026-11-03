from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from .codec import Codec
from .codecs import Codecs
from .error import ModelError, qualified
from .model import Model
from .models import Models

if TYPE_CHECKING:
	from .namespaces import Namespaces


@dataclass(init=False)
class Namespace:
	"""Models by class name and codecs by the type they convert.

	A lookup checks this namespace, then its parent.
	"""

	namespaces: Namespaces
	models: Models
	codecs: Codecs

	def __init__(self, namespaces: Namespaces, parent: Namespace | None = None):
		self.namespaces = namespaces
		if parent is None:
			self.models = Models()
			self.codecs = Codecs()
		else:
			self.models = Models(parent.models)
			self.codecs = Codecs(parent.codecs)

	def model(self, model_type: type[Model]):
		if self.namespaces.find(model_type) is not None:
			raise ModelError(f"{qualified(model_type)} is already registered")

		self.models.model(model_type)
		self.namespaces.model(model_type, self)

	def codec(self, codec: Codec[Any]):
		self.codecs.codec(codec)
