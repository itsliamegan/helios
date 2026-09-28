from typing import Any

from helios.app import Context
from helios.http import Response, Status

from .engine import Engine
from .view import View


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
			self.engine.render(view, assigns),
			status,
		)
