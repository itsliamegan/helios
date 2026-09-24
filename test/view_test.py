from datetime import UTC, datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import TemplateNotFound, TemplateSyntaxError, UndefinedError
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.app import Application, Config, Container, Context
from helios.http import Method, Request, Status, URL
from helios.routing import Pattern, Route, Router
import helios.view
from helios.view import Engine, Helpers, Views, file, helpers, memory


def test_renders_simple():
	engine = Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"}))

	html = engine.render("index", {"title": "Index"})

	assert_eq(html, "<h1>Index</h1>")


def test_renders_inherited():
	engine = Engine(
		memory.Driver(
			{
				"base": "<h1>{{ title }}</h1>{% block content %}{% endblock %}",
				"show": '{% extends "base" %}{% block content %}<p>An article.</p>{% endblock %}',
			}
		)
	)

	html = engine.render("show", {"title": "Intro"})

	assert_eq(html, "<h1>Intro</h1><p>An article.</p>")


def test_renders_application_filters():
	engine = Engine(
		memory.Driver({"index": "{{ title | shout }}"}),
		Helpers(filters={"shout": lambda text: text.upper() + "!"}),
	)

	html = engine.render("index", {"title": "hello"})

	assert_eq(html, "HELLO!")


def test_renders_application_globals():
	engine = Engine(
		memory.Driver({"index": "{{ greet(name) }} from {{ site }}"}),
		Helpers(globals={"greet": lambda name: f"Hi {name}", "site": "Cork"}),
	)

	html = engine.render("index", {"name": "Ada"})

	assert_eq(html, "Hi Ada from Cork")


def test_keeps_default_filters_alongside_application_filters():
	engine = Engine(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"shout": lambda text: text.upper()}),
	)

	html = engine.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "Apr 7, 2026")


def test_application_filters_override_defaults():
	engine = Engine(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"date": lambda day: day.strftime("%Y-%m-%d")}),
	)

	html = engine.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "2026-04-07")


def test_escapes_plain_string_helper_output():
	engine = Engine(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: f"<b>{text}</b>"}),
	)

	html = engine.render("index", {"title": "Hi"})

	assert_eq(html, "&lt;b&gt;Hi&lt;/b&gt;")


def test_renders_markup_helper_output_unescaped():
	engine = Engine(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: Markup("<b>{}</b>").format(text)}),
	)

	html = engine.render("index", {"title": "<i>"})

	assert_eq(html, "<b>&lt;i&gt;</b>")


def test_directory_renders_application_helpers():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("{{ site }}")

		engine = Engine(file.Driver(views_dir), Helpers(globals={"site": "Cork"}))

		assert_eq(engine.render("index"), "Cork")


def test_renders_nested_directory_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("<h1>Boards</h1>")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("boards.index"), "<h1>Boards</h1>")


def test_directory_rejects_syntax_errors_on_creation():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "show.html").write_text("<h1>Show</h1>")
		broken_file = views_dir.joinpath("boards", "index.html")
		broken_file.write_text("<h1>{{ title }}</h1>\n{% if title %}\n")

		with assert_raises(TemplateSyntaxError) as raised:
			Engine(file.Driver(views_dir))

		exception = raised.exception
		assert exception is not None
		assert_eq(exception.filename, str(broken_file))
		assert_eq(exception.lineno, 2)


def test_directory_rejects_names_outside_directory():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir, "engine")
		views_dir.mkdir()
		Path(dir, "secret.html").write_text("secret")
		engine = Engine(file.Driver(views_dir))

		with assert_raises(TemplateNotFound):
			engine.render("..secret")


def test_directory_reloads_changed_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		engine = Engine(file.Driver(views_dir), reload=True)

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(engine.render("index"), "After")


def test_directory_rejects_deleted_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Index")
		engine = Engine(file.Driver(views_dir), reload=True)

		template_file.unlink()

		with assert_raises(TemplateNotFound):
			engine.render("index")


def test_memory_reloads_changed_templates_when_reloading():
	templates = {"index": "Before"}
	engine = Engine(memory.Driver(templates), reload=True)

	templates["index"] = "After"

	assert_eq(engine.render("index"), "After")


def test_directory_keeps_compiled_templates_when_not_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		engine = Engine(file.Driver(views_dir))

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(engine.render("index"), "Before")


def test_directory_ignores_hidden_files():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		views_dir.joinpath(".#index.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("index"), "<h1>Index</h1>")


def test_directory_ignores_hidden_directories():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		hidden_dir = views_dir.joinpath(".drafts")
		hidden_dir.mkdir()
		hidden_dir.joinpath("show.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("index"), "<h1>Index</h1>")


def test_escapes_assigns():
	engine = Engine(memory.Driver({"posts.index": "<h1>{{ title }}</h1>"}))

	html = engine.render("posts.index", {"title": "<script>alert(1)</script>"})

	assert_eq(html, "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>")


def test_escapes_assigns_in_loaded_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("{{ title }}")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("boards.index", {"title": "<b>"}), "&lt;b&gt;")


def test_rejects_undefined_variables():
	engine = Engine(memory.Driver({"index": "<h1>{{ titel }}</h1>"}))

	with assert_raises(UndefinedError):
		engine.render("index", {"title": "Index"})


def test_rejects_undefined_attributes():
	engine = Engine(memory.Driver({"index": "<h1>{{ board.titel }}</h1>"}))

	with assert_raises(UndefinedError):
		engine.render("index", {"board": {"title": "Index"}})


def test_rejects_undefined_variables_in_conditions():
	engine = Engine(memory.Driver({"index": "{% if error %}{{ error }}{% endif %}"}))

	with assert_raises(UndefinedError):
		engine.render("index")


def test_renders_none_variables_in_conditions():
	engine = Engine(memory.Driver({"index": "{% if error %}{{ error }}{% endif %}"}))

	html = engine.render("index", {"error": None})

	assert_eq(html, "")


def test_views_render_html_responses():
	views = Views(Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"})), context())

	response = views.render("index", {"title": "Index"})

	assert_eq(response.status, Status.OK)
	assert_eq(str(response.headers["Content-Type"]), "text/html")
	assert_eq(str(response.body), "<h1>Index</h1>")


def test_views_render_responses_with_status():
	views = Views(Engine(memory.Driver({"missing": "<h1>Not found</h1>"})), context())

	response = views.render("missing", status=Status.NOT_FOUND)

	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(str(response.body), "<h1>Not found</h1>")


def test_views_render_composer_assigns():
	engine = Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"}))
	engine.composer(lambda view, context: view.assign("title", "Composed"))
	views = Views(engine, context())

	response = views.render("index")

	assert_eq(str(response.body), "<h1>Composed</h1>")


def test_views_pass_context_and_view_to_composers():
	engine = Engine(memory.Driver({"index": "{{ name }} {{ path }}"}))
	engine.composer(lambda view, context: view.assign("name", view.name))
	engine.composer(lambda view, context: view.assign("path", str(context.request.url)))
	views = Views(engine, context())

	response = views.render("index")

	assert_eq(str(response.body), "index /")


def test_views_run_composers_in_registration_order():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	engine.composer(lambda view, context: view.assign("title", "First"))
	engine.composer(lambda view, context: view.assign("title", "Second"))
	views = Views(engine, context())

	response = views.render("index")

	assert_eq(str(response.body), "Second")


def test_views_prefer_assigns_over_composers():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	engine.composer(lambda view, context: view.assign("title", "Composed"))
	views = Views(engine, context())

	response = views.render("index", {"title": "Assigned"})

	assert_eq(str(response.body), "Assigned")


def test_engine_renders_without_composers():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	engine.composer(lambda view, context: view.assign("title", "Composed"))

	with assert_raises(UndefinedError):
		engine.render("index")


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


def test_formats_elapsed_seconds():
	then = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=0, tzinfo=UTC)
	now = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=25, tzinfo=UTC)

	assert_eq(helpers.elapsed(then, now), "less than a minute ago")


def test_formats_elapsed_minutes():
	then = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=0, tzinfo=UTC)
	now = datetime(year=2025, month=9, day=1, hour=12, minute=30, second=0, tzinfo=UTC)

	assert_eq(helpers.elapsed(then, now), "30 minutes ago")


def test_formats_elapsed_hours():
	then = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=0, tzinfo=UTC)
	now = datetime(year=2025, month=9, day=1, hour=14, minute=10, second=0, tzinfo=UTC)

	assert_eq(helpers.elapsed(then, now), "2 hours ago")


def test_formats_elapsed_days():
	then = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=0, tzinfo=UTC)
	now = datetime(year=2025, month=9, day=3, hour=14, minute=0, second=0, tzinfo=UTC)

	assert_eq(helpers.elapsed(then, now), "2 days ago")


def test_formats_then_if_elapsed_over_a_week():
	then = datetime(year=2025, month=9, day=1, hour=12, minute=0, second=0, tzinfo=UTC)
	now = datetime(year=2025, month=9, day=8, hour=12, minute=0, second=0, tzinfo=UTC)

	assert_eq(helpers.elapsed(then, now), "Sep 1, 2025")


def test_formats_date():
	date = datetime(year=2026, month=4, day=7, tzinfo=UTC)

	assert_eq(helpers.date(date), "Apr 7, 2026")


def context() -> Context:
	return Context(Container(), Request(Method.GET, URL("/")))
