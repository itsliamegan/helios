from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import UndefinedError
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view import Engine, Helpers, file, memory


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


def test_engine_renders_without_composers():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	engine.composer(lambda view, context: view.assign("title", "Composed"))

	with assert_raises(UndefinedError):
		engine.render("index")
