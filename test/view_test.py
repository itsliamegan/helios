from datetime import UTC, datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import TemplateNotFound, TemplateSyntaxError
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.http import URL
from helios.view import Helpers, Views, file, helpers, memory


def test_renders_simple():
	views = Views(memory.Driver({"index": "<h1>{{ title }}</h1>"}))

	html = views.render("index", {"title": "Index"})

	assert_eq(html, "<h1>Index</h1>")


def test_renders_inherited():
	views = Views(
		memory.Driver(
			{
				"base": "<h1>{{ title }}</h1>{% block content %}{% endblock %}",
				"show": '{% extends "base" %}{% block content %}<p>An article.</p>{% endblock %}',
			}
		)
	)

	html = views.render("show", {"title": "Intro"})

	assert_eq(html, "<h1>Intro</h1><p>An article.</p>")


def test_renders_application_filters():
	views = Views(
		memory.Driver({"index": "{{ title | shout }}"}),
		Helpers(filters={"shout": lambda text: text.upper() + "!"}),
	)

	html = views.render("index", {"title": "hello"})

	assert_eq(html, "HELLO!")


def test_renders_application_globals():
	views = Views(
		memory.Driver({"index": "{{ greet(name) }} from {{ site }}"}),
		Helpers(globals={"greet": lambda name: f"Hi {name}", "site": "Cork"}),
	)

	html = views.render("index", {"name": "Ada"})

	assert_eq(html, "Hi Ada from Cork")


def test_keeps_default_filters_alongside_application_filters():
	views = Views(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"shout": lambda text: text.upper()}),
	)

	html = views.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "Apr 7, 2026")


def test_application_filters_override_defaults():
	views = Views(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"date": lambda day: day.strftime("%Y-%m-%d")}),
	)

	html = views.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "2026-04-07")


def test_escapes_plain_string_helper_output():
	views = Views(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: f"<b>{text}</b>"}),
	)

	html = views.render("index", {"title": "Hi"})

	assert_eq(html, "&lt;b&gt;Hi&lt;/b&gt;")


def test_renders_markup_helper_output_unescaped():
	views = Views(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: Markup("<b>{}</b>").format(text)}),
	)

	html = views.render("index", {"title": "<i>"})

	assert_eq(html, "<b>&lt;i&gt;</b>")


def test_directory_renders_application_helpers():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("{{ site }}")

		views = Views(file.Driver(views_dir), Helpers(globals={"site": "Cork"}))

		assert_eq(views.render("index"), "Cork")


def test_renders_nested_directory_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("<h1>Boards</h1>")

		views = Views(file.Driver(views_dir))

		assert_eq(views.render("boards.index"), "<h1>Boards</h1>")


def test_directory_rejects_syntax_errors_on_creation():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "show.html").write_text("<h1>Show</h1>")
		broken_file = views_dir.joinpath("boards", "index.html")
		broken_file.write_text("<h1>{{ title }}</h1>\n{% if title %}\n")

		with assert_raises(TemplateSyntaxError) as raised:
			Views(file.Driver(views_dir))

		exception = raised.exception
		assert exception is not None
		assert_eq(exception.filename, str(broken_file))
		assert_eq(exception.lineno, 2)


def test_directory_rejects_names_outside_directory():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir, "views")
		views_dir.mkdir()
		Path(dir, "secret.html").write_text("secret")
		views = Views(file.Driver(views_dir))

		with assert_raises(TemplateNotFound):
			views.render("..secret")


def test_directory_reloads_changed_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		views = Views(file.Driver(views_dir), reload=True)

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(views.render("index"), "After")


def test_directory_rejects_deleted_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Index")
		views = Views(file.Driver(views_dir), reload=True)

		template_file.unlink()

		with assert_raises(TemplateNotFound):
			views.render("index")


def test_memory_reloads_changed_templates_when_reloading():
	templates = {"index": "Before"}
	views = Views(memory.Driver(templates), reload=True)

	templates["index"] = "After"

	assert_eq(views.render("index"), "After")


def test_directory_keeps_compiled_templates_when_not_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		views = Views(file.Driver(views_dir))

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(views.render("index"), "Before")


def test_directory_ignores_hidden_files():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		views_dir.joinpath(".#index.html").write_bytes(b"\xff")

		views = Views(file.Driver(views_dir))

		assert_eq(views.render("index"), "<h1>Index</h1>")


def test_directory_ignores_hidden_directories():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		hidden_dir = views_dir.joinpath(".drafts")
		hidden_dir.mkdir()
		hidden_dir.joinpath("show.html").write_bytes(b"\xff")

		views = Views(file.Driver(views_dir))

		assert_eq(views.render("index"), "<h1>Index</h1>")


def test_escapes_assigns():
	views = Views(memory.Driver({"posts.index": "<h1>{{ title }}</h1>"}))

	html = views.render("posts.index", {"title": "<script>alert(1)</script>"})

	assert_eq(html, "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>")


def test_escapes_assigns_in_loaded_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("{{ title }}")

		views = Views(file.Driver(views_dir))

		assert_eq(views.render("boards.index", {"title": "<b>"}), "&lt;b&gt;")


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


def test_formats_url_with_breaks():
	url = URL("/posts/1354")

	assert_eq(str(helpers.url(url)), "/<wbr>posts/<wbr>1354")
