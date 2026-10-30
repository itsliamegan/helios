import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_is, assert_not_none

from helios.app import Application, Config
from helios.assets import Manifest
import helios.assets.config
import helios.assets.provider
from helios.http import Method, Request
from helios.routing import Route, Router
from helios.url import URL
import helios.view.config
import helios.view.provider
from helios.view.views import Views


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
			[helios.view.provider.Provider(helios.view.config.Config(views_dir))],
		)
		app.boot()
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(str(response.body), '<a href="/posts/7">Post</a>')


def test_provider_shares_current_route_with_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("show.html").write_text(
			'{% if urls.route_is("posts.*") %}active{% endif %}'
		)

		def show(request, context, id):
			return context.get(Views).render("show")

		app = Application(
			Config(URL.parse("https://example.com")),
			Router([Route.get("/posts/{id}", show, name="posts.show")]),
			[helios.view.provider.Provider(helios.view.config.Config(views_dir))],
		)
		app.boot()
		try:
			response = app.handle(Request(Method.GET, URL("/posts/7")))
		finally:
			app.close()

	assert_eq(str(response.body), "active")


def test_provider_shares_assets_with_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir, "views")
		views_dir.mkdir()
		views_dir.joinpath("index.html").write_text('{{ assets.script("main") }}')
		assets = helios.assets.config.Config(
			Path(dir, "assets"),
			Path(dir, "public", "assets"),
			scripts=["main"],
			styles=[],
		)
		assets.manifest.parent.mkdir(parents=True)
		Manifest(scripts={"main": "scripts/main.js"}, styles={}).save(assets.manifest)

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			Config(),
			Router([Route.get("/", index)]),
			[
				helios.assets.provider.Provider(assets),
				helios.view.provider.Provider(helios.view.config.Config(views_dir)),
			],
		)
		app.boot()
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(
		str(response.body),
		'<script type="module" src="/assets/scripts/main.js"></script>',
	)


def test_provider_registers_components():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("tags").mkdir()
		views_dir.joinpath("tags", "chip.py").write_text(
			"from helios.view import Component\n"
			"\n"
			"\n"
			"class TagChip(Component):\n"
			'\ttemplate = "tags/chip"\n'
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
				helios.view.provider.Provider(
					helios.view.config.Config(views_dir),
					components=[chip.TagChip],
				)
			],
		)
		app.boot()
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(
		str(response.body),
		'<span class="chip">Travel</span><span class="chip">Food</span>',
	)


def test_provider_registers_config_before_boot():
	with TemporaryDirectory() as dir:
		config = helios.view.config.Config(Path(dir))

		app = Application(Config(), Router([]), [helios.view.provider.Provider(config)])

		assert_is(app.container.get(helios.view.config.Config), config)
