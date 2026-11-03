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
		self.namespaces = Namespaces()
		for codec in CODECS:
			self.codec(codec)

	def model(self, model_type: type[Model]):
		self.namespaces.root.model(model_type)

	def codec(self, codec: Codec[Any]):
		self.namespaces.root.codec(codec)

	def namespace(self, name: str) -> Namespace:
		return self.namespaces.namespace(name)


class Namespaces:
	"""The root namespace, the named namespaces, and each model's namespace.

	A model is registered in exactly one namespace of a registry.
	"""

	def __init__(self):
		self.root = Namespace(self)
		self.named: dict[str, Namespace] = {}
		self.registered: dict[type[Model], Namespace] = {}

	def namespace(self, name: str) -> Namespace:
		if name in self.named:
			raise ModelError(f"namespace {name!r} is already registered")

		namespace = Namespace(self, parent=self.root)
		self.named[name] = namespace
		return namespace

	def model(self, model_type: type[Model], namespace: Namespace):
		self.registered[model_type] = namespace

	def find(self, model_type: type[Model]) -> Namespace | None:
		return self.registered.get(model_type)


class Namespace:
	"""Models and codecs registered together, looked up before the parent's."""

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


class Models:
	"""Models by class name, looked up before the parent's.

	A pending annotation on one of these models resolves names through them.
	"""

	def __init__(self, parent: Models | None = None):
		self.parent = parent
		self.named: dict[str, type[Model]] = {}

	def model(self, model_type: type[Model]):
		if not isinstance(model_type, type) or not issubclass(model_type, Model):
			raise ModelError("registered model must be a Model subclass")
		if not isinstance(model_type.table, str) or not model_type.table:
			raise ModelError(f"{model_type.__name__} must declare a non-empty table")

		named = self.named.get(model_type.__name__)
		if named is not None:
			raise ModelError(
				f"registered models share the name {model_type.__name__}: "
				f"{qualified(named)}, {qualified(model_type)}"
			)

		self.named[model_type.__name__] = model_type
		for declaration in model_type.pending_declarations():
			declaration.fallback = self

	def find(self, name: str) -> type[Model] | None:
		found = self.named.get(name)
		if found is None and self.parent is not None:
			return self.parent.find(name)
		else:
			return found


class Codecs:
	"""Codecs by the type they convert, looked up before the parent's."""

	def __init__(self, parent: Codecs | None = None):
		self.parent = parent
		self.converted: dict[object, Codec[Any]] = {}

	def codec(self, codec: Codec[Any]):
		registered = self.converted.get(codec.converts)
		if registered is not None:
			raise ModelError(
				f"registered codecs share the type {codec.converts.__name__}: "
				f"{qualified(type(registered))}, {qualified(type(codec))}"
			)

		self.converted[codec.converts] = codec

	def find(self, annotation: object) -> Codec[Any] | None:
		"""Return the codec for an annotation without `| None`.

		The codec is the one registered for the annotation's origin when it has
		one, or for the annotation itself otherwise.
		"""

		found = self.converted.get(get_origin(annotation) or annotation)
		if found is None and self.parent is not None:
			return self.parent.find(annotation)
		else:
			return found


def qualified(named: type) -> str:
	return f"{named.__module__}.{named.__qualname__}"
