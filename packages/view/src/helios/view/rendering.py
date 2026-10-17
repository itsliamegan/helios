from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from jinja2 import TemplateRuntimeError
from markupsafe import Markup

if TYPE_CHECKING:
	from .engine import Engine

current: ContextVar[Rendering] = ContextVar("current")


@dataclass(init=False)
class Rendering:
	"""A single view being rendered, updated as the layout chain is walked."""

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
			raise TemplateRuntimeError(f'Section "{name}" is set twice')

		if content.strip():
			self.sections[name] = content
		else:
			self.sections[name] = None


class Sections:
	"""The named sections set by a view.

	Sections can be read by attribute or item lookup. An unset section and an
	empty section are both None.
	"""

	def __init__(self, sections: Mapping[str, Markup | None]):
		self._sections = dict(sections)

	def __getitem__(self, name: str) -> Markup | None:
		# Jinja reads sections.title through this too, after attribute lookup
		# finds nothing.
		return self._sections.get(name)
