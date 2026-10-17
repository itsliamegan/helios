from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from jinja2 import TemplateRuntimeError
from markupsafe import Markup

if TYPE_CHECKING:
	from .engine import Engine


@dataclass(init=False)
class Rendering:
	"""The state of one view's render, through its chain of layouts.

	The template rendering now names its layout at most once, and each section
	is set once in the whole chain.
	"""

	engine: Engine
	shared: dict[str, Any]
	layout: str | None
	sections: dict[str, Markup | None]

	def __init__(self, engine: Engine, shared: Mapping[str, Any]):
		self.engine = engine
		self.shared = dict(shared)
		self.layout = None
		self.sections = {}

	def set_layout(self, name: str):
		if self.layout is not None:
			raise TemplateRuntimeError("A view names its layout twice")
		self.layout = name

	def set_section(self, name: str, content: Markup):
		if name in self.sections:
			raise TemplateRuntimeError(f'The section "{name}" is set twice')

		if content.strip():
			self.sections[name] = content
		else:
			self.sections[name] = None


rendering: ContextVar[Rendering] = ContextVar("rendering")


class Sections:
	"""The sections set below a layout, read by name as attributes or keys.

	An unset section is nothing, and so is an empty one.
	"""

	def __init__(self, sections: Mapping[str, Markup | None]):
		for name, content in sections.items():
			setattr(self, name, content)

	def __getattr__(self, name: str):
		# Lookup finds a section that is set before reaching here, but special
		# names such as __html__ must stay missing for MarkupSafe and copying.
		if name.startswith("__"):
			raise AttributeError(name)

	def __getitem__(self, name: str) -> Markup | None:
		return getattr(self, name)
