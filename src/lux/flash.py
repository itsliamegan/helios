from typing import Any

from lux.app import Component, Context
from lux.http import Request, Response

class Component(Component):
	def before(self, req: Request, ctx: Context):
		if "_flash" in ctx.session:
			flashes = Flashes(ctx.session["_flash"])
			del ctx.session["_flash"]
		else:
			flashes = Flashes()
		ctx.flash = flashes

	def after(self, res: Response, ctx: Context):
		if ctx.flash.is_dirty():
			ctx.session["_flash"] = ctx.flash.dirty()

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
		return f"Flash({repr(self.flashes)})"

class Flash:
	def __init__(self, name: str, val: Any):
		self.name = name
		self.val = val
		self.is_dirty = False
