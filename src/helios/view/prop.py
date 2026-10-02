from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from helios.declarative import Declaration, MISSING

if TYPE_CHECKING:
	from .component import Component


@dataclass
class Prop:
	declaration: Declaration

	@property
	def name(self) -> str:
		return self.declaration.name

	@property
	def default(self) -> object:
		return self.declaration.default

	@property
	def required(self) -> bool:
		return self.default is MISSING

	def resolve(self):
		self.declaration.resolve()

	def __get__(self, component: Component | None, owner: type) -> Any:
		if component is None:
			return self

		try:
			return component._values[self.name]
		except KeyError:
			raise AttributeError(
				f"{owner.__name__}.{self.name} has not been initialized"
			) from None

	def __set__(self, component: Component, value: object):
		component._values[self.name] = value
