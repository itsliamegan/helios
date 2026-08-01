from jinja2 import DictLoader, Environment, select_autoescape
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from helios.app import Component, Context
from helios.http import Request
from . import helpers

class Component(Component):
	def __init__(self, dir: Path):
		self.dir = dir
		self.engine = None

	def boot(self):
		self.engine = load(self.dir)

	def before(self, req: Request, ctx: Context):
		ctx.views = self.engine

class Views:
	def __init__(self, tmpls: dict[str, str] | None = None):
		if tmpls is None:
			tmpls = {}
		self.jinja = Environment(
			loader = DictLoader(tmpls),
			autoescape = select_autoescape
		)
		self.jinja.filters["date"] = helpers.date
		self.jinja.filters["url"] = helpers.url
		self.jinja.filters["elapsed"] = helpers.elapsed

	def render(self, name: str, assigns: dict[str, Any] | None = None) -> str:
		if assigns is None:
			assigns = {}
		tmpl = self.jinja.get_template(name)
		return tmpl.render(**assigns)

def load(views_dir: Path) -> Views:
	tmpls = {}
	for (dir, dirs, files) in views_dir.walk():
		parts = dir.relative_to(views_dir).parts
		for file in files:
			path = dir.joinpath(file)
			if path.suffix == ".html":
				name = ".".join(parts + (path.stem,))
				with open(path, "r") as stream:
					src = stream.read()
					tmpls[name] = src
	return Views(tmpls)
