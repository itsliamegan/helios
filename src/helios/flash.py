from __future__ import annotations

from typing import Any

from helios.app import Application, Container, Context, Next, Provider
from helios.http import Request, Response
from helios.session.store import Session
from helios.view import Engine, View


class Flashes:
	def __init__(self, flashes: dict[str, Any] | None = None):
		self.flashes = {name: Flash(name, val) for name, val in (flashes or {}).items()}

	def dirty(self) -> dict[str, Any]:
		return {
			name: flash.val for name, flash in self.flashes.items() if flash.is_dirty
		}

	def is_dirty(self) -> bool:
		return any(flash.is_dirty for flash in self.flashes.values())

	def __getitem__(self, name: str) -> Any:
		return self.flashes[name].val

	def get(self, name: str, default: Any = None) -> Any:
		if name in self.flashes:
			return self.flashes[name].val
		else:
			return default

	def __setitem__(self, name: str, val: Any):
		self.flashes[name] = Flash(name, val)
		self.flashes[name].is_dirty = True

	def __contains__(self, name: str) -> bool:
		return name in self.flashes

	def __repr__(self) -> str:
		return f"Flashes({self.flashes!r})"


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
		if application.container.bound(Engine):
			application.container.get(Engine).composer(self.compose)

	def flashes(self, context: Context) -> Flashes:
		session = context.get(Session)
		if "_flash" in session:
			flashes = Flashes(session["_flash"])
			del session["_flash"]
			return flashes
		return Flashes()

	def compose(self, view: View, context: Context):
		view.assign("flash", context.get(Flashes))

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		flashes = context.resolved(Flashes)
		if flashes is not None and flashes.is_dirty():
			context.get(Session)["_flash"] = flashes.dirty()
		return response
