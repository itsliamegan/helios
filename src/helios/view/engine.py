from pathlib import Path
from typing import Any

from jinja2 import DictLoader, Environment

from .helpers import Helpers


class Views:
	def __init__(
		self,
		tmpls: dict[str, str] | None = None,
		helpers: Helpers | None = None,
	):
		if tmpls is None:
			tmpls = {}
		self.jinja = Environment(loader=DictLoader(tmpls), autoescape=True)
		self.helpers = Helpers.defaults()
		self.helpers.update(helpers or Helpers())
		self.jinja.filters.update(self.helpers.filters)
		self.jinja.globals.update(self.helpers.globals)

	def render(self, name: str, assigns: dict[str, Any] | None = None) -> str:
		if assigns is None:
			assigns = {}
		tmpl = self.jinja.get_template(name)
		return tmpl.render(**assigns)


def load(views_dir: Path, helpers: Helpers | None = None) -> Views:
	tmpls = {}
	for dir, _, files in views_dir.walk():
		if dir.name.startswith("."):
			continue
		parts = dir.relative_to(views_dir).parts
		for file in files:
			if file.startswith("."):
				continue
			path = dir.joinpath(file)
			if path.suffix == ".html":
				name = ".".join(parts + (path.stem,))
				with open(path, "r") as stream:
					src = stream.read()
					tmpls[name] = src
	return Views(tmpls, helpers)
