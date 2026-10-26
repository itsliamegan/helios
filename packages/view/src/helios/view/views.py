from collections.abc import Mapping
from typing import Any

from helios.app import Context
from helios.http import Response, Status

from .composer import Composers
from .engine import Engine
from .view import View


class Views:
	"""Renders a request's views as responses with composed values."""

	def __init__(self, engine: Engine, composers: Composers, context: Context):
		self.engine = engine
		self.composers = composers
		self.context = context

	def render(
		self,
		name: str,
		assigns: Mapping[str, Any] | None = None,
		status: Status = Status.OK,
	) -> Response:
		view = View(name)
		self.composers.compose(view, self.context)
		return Response.html(
			self.engine.render(view, assigns),
			status,
		)
