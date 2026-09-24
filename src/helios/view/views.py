from typing import Any

from helios.http import Response, Status

from .engine import Engine


class Views:
	def __init__(self, engine: Engine):
		self.engine = engine

	def render(
		self,
		name: str,
		assigns: dict[str, Any] | None = None,
		status: Status = Status.OK,
	) -> Response:
		return Response.html(self.engine.render(name, assigns), status)
