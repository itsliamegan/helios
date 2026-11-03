from typing import Any, get_origin

from .codec import CODECS, Codec
from .error import ModelError
from .model import Model


class Registry:
	"""The models and codecs registered for a single database.

	The registry is made up of the root namespace and a set of named
	namespaces. The root namespace contains the core codecs and those that an
	application declares. Each named namespace contains models and codecs of
	its own. A lookup from a named namespace first checks its own registrations
	before checking the root.
	"""

	def __init__(self):
		self.model_types: set[type[Model]] = set()
		self.root = Namespace(self)
		self.namespaces: dict[str, Namespace] = {}
		for codec in CODECS:
			self.root.codec(codec)

	def model(self, model_type: type[Model]):
		self.root.model(model_type)

	def codec(self, codec: Codec[Any]):
		self.root.codec(codec)

	def namespace(self, name: str) -> Namespace:
		if name in self.namespaces:
			raise ModelError(f"namespace {name!r} is already registered")

		namespace = Namespace(self, parent=self.root)
		self.namespaces[name] = namespace
		return namespace

	def get[T: Model](self, model_type: type[T]) -> type[T]:
		if model_type not in self.model_types:
			raise ModelError(f"{model_type.__name__} is not a registered model")
		return model_type


class Namespace:
	"""Models by class name and codecs by the type they convert.

	A lookup checks this namespace, then its parent.
	"""

	def __init__(self, registry: Registry, parent: Namespace | None = None):
		self.registry = registry
		self.parent = parent
		self.models: dict[str, type[Model]] = {}
		self.codecs: dict[object, Codec[Any]] = {}

	def model(self, model_type: type[Model]):
		if not isinstance(model_type, type) or not issubclass(model_type, Model):
			raise ModelError("registered model must be a Model subclass")
		if not isinstance(model_type.table, str) or not model_type.table:
			raise ModelError(f"{model_type.__name__} must declare a non-empty table")
		if model_type in self.registry.model_types:
			raise ModelError(f"{qualified(model_type)} is already registered")

		named = self.models.setdefault(model_type.__name__, model_type)
		if named is not model_type:
			raise ModelError(
				f"registered models share the name {model_type.__name__}: "
				f"{qualified(named)}, {qualified(model_type)}"
			)

		self.registry.model_types.add(model_type)
		model_type.bind_namespace(self)

	def codec(self, codec: Codec[Any]):
		registered = self.codecs.get(codec.converts)
		if registered is not None:
			raise ModelError(
				f"registered codecs share the type {codec.converts.__name__}: "
				f"{qualified(type(registered))}, {qualified(type(codec))}"
			)

		self.codecs[codec.converts] = codec

	def codec_for(self, annotation: object) -> Codec[Any] | None:
		"""Return the codec for an annotation without `| None`.

		The codec is the one registered for the annotation's origin when it has
		one, or for the annotation itself otherwise.
		"""

		found = self.codecs.get(get_origin(annotation) or annotation)
		if found is None and self.parent is not None:
			return self.parent.codec_for(annotation)
		else:
			return found

	def find(self, name: str) -> type[Model] | None:
		found = self.models.get(name)
		if found is None and self.parent is not None:
			return self.parent.find(name)
		else:
			return found


def qualified(named: type) -> str:
	return f"{named.__module__}.{named.__qualname__}"
