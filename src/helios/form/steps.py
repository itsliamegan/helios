from dataclasses import dataclass
from typing import TYPE_CHECKING

from .error import FormError
from .key import ITEM, Key

if TYPE_CHECKING:
	from .form import Form


@dataclass(init=False)
class Steps[T]:
	item: dict[str, list[T]]
	field: dict[str, list[T]]

	def __init__(self, declared: dict[str, list[T]] | None = None):
		self.item = {}
		self.field = {}
		for text, steps in (declared or {}).items():
			key = Key.parse(text)
			if key.rest:
				raise FormError(
					f"{type(self).__name__} has '{text}', which is neither "
					f"'{key.name}' nor '{key.name}.{ITEM}'"
				)
			elif key.item:
				self.item[key.name] = steps
			else:
				self.field[key.name] = steps

	def verify(self, form: type[Form]):
		kind = type(self).__name__.lower()
		for name in [*self.item, *self.field]:
			if name not in form.fields:
				raise FormError(
					f"Form {form.__name__} has {kind} for '{name}', which is not a field"
				)

		for name in self.item:
			if not form.fields[name].is_list:
				raise FormError(
					f"Form {form.__name__} has {kind} for '{name}.{ITEM}', "
					f"but '{name}' is not a list"
				)
