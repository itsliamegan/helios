from typing import Any

from .codec import CODECS, Codec
from .model import Model
from .namespace import Namespace
from .namespaces import Namespaces


class Registry:
	"""The models and codecs registered for a single database.

	The registry is made up of the root namespace and a set of named
	namespaces. The root namespace contains the core codecs as well as the
	models and codecs that an application declares. Each named namespace
	contains models and codecs of its own. A lookup from a named namespace first checks its own registrations
	before checking the root.
	"""

	def __init__(self):
		self.namespaces = Namespaces()
		for codec in CODECS:
			self.codec(codec)

	def model(self, model_type: type[Model]):
		self.namespaces.root.model(model_type)

	def codec(self, codec: Codec[Any]):
		self.namespaces.root.codec(codec)

	def namespace(self, name: str) -> Namespace:
		return self.namespaces.namespace(name)
