from __future__ import annotations

from typing import Any

from helios.app import Component, Context
from helios.http import Response
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


class Component(Component[Flashes]):
	provides = Flashes
	requires = (Session,)

	def provide(self, ctx: Context) -> Flashes:
		session = ctx.get(Session)

		if "_flash" in session:
			flashes = Flashes(session["_flash"])
			del session["_flash"]
		else:
			flashes = Flashes()
		return flashes

	def finish(self, res: Response, ctx: Context):
		flashes = ctx.get(Flashes)
		session = ctx.get(Session)

		if flashes.is_dirty():
			session["_flash"] = flashes.dirty()
