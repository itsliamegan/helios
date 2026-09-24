import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq

from helios.app import Application, Config
from helios.http import Method, Request, URL
from helios.routing import Pattern, Route, Router
import helios.view
from helios.view import Views


def test_provider_shares_urls_with_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text(
			'<a href="{{ urls.route("boards.show", {"id": 7}) }}">Board</a>'
		)

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			Config(URL("https://example.com")),
			Router(
				[
					Route(Method.GET, Pattern("/"), index),
					Route(
						Method.GET,
						Pattern("/boards/{id}"),
						index,
						name="boards.show",
					),
				]
			),
			[helios.view.Provider(helios.view.Config(views_dir))],
		)
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(str(response.body), '<a href="/boards/7">Board</a>')


def test_provider_registers_components():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "chip.py").write_text(
			"from dataclasses import dataclass\n"
			"\n"
			"from helios.view import Component\n"
			"\n"
			"\n"
			"@dataclass(kw_only=True)\n"
			"class BoardChip(Component):\n"
			'\ttemplate = "boards.chip"\n'
			"\n"
			"\tname: str\n"
		)
		views_dir.joinpath("boards", "chip.html").write_text(
			'<span class="chip">{{ name }}</span>'
		)
		views_dir.joinpath("index.html").write_text(
			"{% for name in names %}{{ BoardChip(name=name) }}{% endfor %}"
		)
		spec = importlib.util.spec_from_file_location(
			"chip",
			views_dir.joinpath("boards", "chip.py"),
		)
		assert spec is not None and spec.loader is not None
		chip = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(chip)

		def index(request, context):
			return context.get(Views).render("index", {"names": ["Travel", "Food"]})

		app = Application(
			Config(URL("https://example.com")),
			Router([Route(Method.GET, Pattern("/"), index)]),
			[
				helios.view.Provider(
					helios.view.Config(views_dir),
					components=[chip.BoardChip],
				)
			],
		)
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(
		str(response.body),
		'<span class="chip">Travel</span><span class="chip">Food</span>',
	)
