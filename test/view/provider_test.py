import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_not_none

from helios.app import Application, Config
from helios.http import Method, Request, URL
from helios.routing import Route, Router
import helios.view
from helios.view import Views


def test_provider_shares_urls_with_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text(
			'<a href="{{ urls.route("posts.show", {"id": 7}) }}">Post</a>'
		)

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			Config(URL.parse("https://example.com")),
			Router(
				[
					Route.get("/", index),
					Route.get(
						"/posts/{id}",
						index,
						name="posts.show",
					),
				]
			),
			[helios.view.Provider(helios.view.Config(views_dir))],
		)
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(str(response.body), '<a href="/posts/7">Post</a>')


def test_provider_registers_components():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("tags").mkdir()
		views_dir.joinpath("tags", "chip.py").write_text(
			"from helios.view import Component\n"
			"\n"
			"\n"
			"class TagChip(Component):\n"
			'\ttemplate = "tags.chip"\n'
			"\n"
			"\tname: str\n"
		)
		views_dir.joinpath("tags", "chip.html").write_text(
			'<span class="chip">{{ name }}</span>'
		)
		views_dir.joinpath("index.html").write_text(
			"{% for name in names %}{{ TagChip(name=name) }}{% endfor %}"
		)
		spec = assert_not_none(
			importlib.util.spec_from_file_location(
				"chip",
				views_dir.joinpath("tags", "chip.py"),
			)
		)
		loader = assert_not_none(spec.loader)
		chip = importlib.util.module_from_spec(spec)
		loader.exec_module(chip)

		def index(request, context):
			return context.get(Views).render("index", {"names": ["Travel", "Food"]})

		app = Application(
			Config(URL.parse("https://example.com")),
			Router([Route.get("/", index)]),
			[
				helios.view.Provider(
					helios.view.Config(views_dir),
					components=[chip.TagChip],
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
