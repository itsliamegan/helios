from dataclasses import dataclass

from .error import ModelError
from .model import Model
from .namespace import Namespace


@dataclass(init=False)
class Namespaces:
	"""The root namespace, the named namespaces, and each model's namespace.

	A model is registered in exactly one namespace per registry.
	"""

	root: Namespace
	named: dict[str, Namespace]
	registered: dict[type[Model], Namespace]

	def __init__(self):
		self.root = Namespace(self)
		self.named = {}
		self.registered = {}

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
