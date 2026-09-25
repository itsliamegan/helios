from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helios.app import Application, Container, Context, Next, Provider
from helios.form import Errors, Submission
from helios.http import Input, Request, Response
from helios.session.store import Session
from helios.view import Engine, View


@dataclass(init=False)
class Flashes:
	flashes: dict[str, Flash]

	def __init__(self, flashes: dict[str, Any] | None = None):
		flashes = flashes or {}
		self.flashes = {}
		for name in flashes:
			self.flashes[name] = Flash(name, flashes[name])

	def dirty(self) -> dict[str, Any]:
		dirty = {}
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				dirty[name] = self.flashes[name].value
		return dirty

	def is_dirty(self) -> bool:
		for name in self.flashes:
			if self.flashes[name].is_dirty:
				return True
		return False

	def __getitem__(self, name: str) -> Any:
		return self.flashes[name].value

	def get(self, name: str, default: Any = None) -> Any:
		if name in self.flashes:
			return self.flashes[name].value
		else:
			return default

	def __setitem__(self, name: str, value: Any):
		self.flashes[name] = Flash(name, value, is_dirty=True)

	def __contains__(self, name: str) -> bool:
		return name in self.flashes

	def errors(self, errors: Errors):
		self["_errors"] = {
			name: list(messages) for name, messages in errors.messages.items()
		}

	def input(self, input: Input):
		self["_input"] = dict(input.items)

	def submission(self) -> Submission:
		input = self.get("_input")
		errors = self.get("_errors")
		return Submission(
			Input(input) if input is not None else None,
			Errors(errors) if errors is not None else None,
		)


@dataclass
class Flash:
	name: str
	value: Any
	is_dirty: bool = False


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
		flashes = context.get(Flashes)
		view.assign("flash", flashes)
		view.assign("submission", flashes.submission())

	def middleware(self, request: Request, context: Context, next: Next) -> Response:
		response = next(request, context)
		flashes = context.resolved(Flashes)
		if flashes is not None and flashes.is_dirty():
			context.get(Session)["_flash"] = flashes.dirty()
		return response
