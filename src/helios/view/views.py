from dataclasses import dataclass
from typing import Any

from helios.app import Context
from helios.http import Response, Status

from .engine import Engine


@dataclass(init=False)
class View:
	name: str
	shared: dict[str, Any]

	def __init__(self, name: str):
		self.name = name
		self.shared = {}

	def share(self, name: str, value: Any):
		self.shared[name] = value


class Views:
	def __init__(self, engine: Engine, context: Context):
		self.engine = engine
		self.context = context

	def render(
		self,
		name: str,
		assigns: dict[str, Any] | None = None,
		status: Status = Status.OK,
	) -> Response:
		view = View(name)
		for composer in self.engine.composers:
			composer(view, self.context)
		return Response.html(
			self.engine.render(view.name, assigns, view.shared),
			status,
		)
