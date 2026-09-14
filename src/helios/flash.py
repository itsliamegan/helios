from __future__ import annotations

from typing import Any

from helios.app import Application, Container, Context, Next, Provider
from helios.http import Request, Response
from helios.session.store import Session


class Flashes:
	def __init__(self, flashes: dict[str, Any] | None = None):
		if flashes is None:
			flashes = {}
		self.flashes = {}
		for name in flashes:
			self.flashes[name] = Flash(name, flashes[name])

	def dirty(self) -> dict[str, Any]:
		dirty = {}
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				dirty[name] = self.flashes[name].val
		return dirty

	def is_dirty(self) -> bool:
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				return True
		return False

	def __getitem__(self, name: str) -> Any:
		return self.flashes[name].val

	def __setitem__(self, name: str, val: Any):
		self.flashes[name] = Flash(name, val)
		self.flashes[name].is_dirty = True

	def __contains__(self, name: str) -> bool:
		return name in self.flashes

	def __repr__(self) -> str:
		return f"Flash({self.flashes!r})"


class Flash:
	def __init__(self, name: str, val: Any):
		self.name = name
		self.val = val
		self.is_dirty = False


class Provider(Provider):
	def register(self, container: Container):
		container.scoped(Flashes, self.flashes)

	def boot(self, application: Application):
		application.use(self.middleware)

	def flashes(self, context: Context) -> Flashes:
		session = context.get(Session)
		if "_flash" in session:
			flashes = Flashes(session["_flash"])
			del session["_flash"]
			return flashes
		return Flashes()

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		flashes = context.resolved(Flashes)
		if flashes is not None and flashes.is_dirty():
			context.get(Session)["_flash"] = flashes.dirty()
		return response
