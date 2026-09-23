from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq
from markupsafe import Markup

from helios.http import URL
from helios.view import Helpers, helpers
from helios.view.engine import Views, load


def test_renders_simple():
	views = Views({"index": "<h1>{{ title }}</h1>"})

	html = views.render("index", {"title": "Index"})

	assert_eq(html, "<h1>Index</h1>")


def test_renders_inherited():
	views = Views(
		{
			"base": "<h1>{{ title }}</h1>{% block content %}{% endblock %}",
			"show": '{% extends "base" %}{% block content %}<p>An article.</p>{% endblock %}',
		}
	)

	html = views.render("show", {"title": "Intro"})

	assert_eq(html, "<h1>Intro</h1><p>An article.</p>")


def test_renders_application_filters():
	views = Views(
		{"index": "{{ title | shout }}"},
		Helpers(filters={"shout": lambda text: text.upper() + "!"}),
	)

	html = views.render("index", {"title": "hello"})

	assert_eq(html, "HELLO!")


def test_renders_application_globals():
	views = Views(
		{"index": "{{ greet(name) }} from {{ site }}"},
		Helpers(globals={"greet": lambda name: f"Hi {name}", "site": "Cork"}),
	)

	html = views.render("index", {"name": "Ada"})

	assert_eq(html, "Hi Ada from Cork")


def test_keeps_default_filters_alongside_application_filters():
	views = Views(
		{"index": "{{ day | date }}"},
		Helpers(filters={"shout": lambda text: text.upper()}),
	)

	html = views.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "Apr 7, 2026")


def test_application_filters_override_defaults():
	views = Views(
		{"index": "{{ day | date }}"},
		Helpers(filters={"date": lambda day: day.strftime("%Y-%m-%d")}),
	)

	html = views.render("index", {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "2026-04-07")


def test_escapes_plain_string_helper_output():
	views = Views(
		{"index": "{{ title | bold }}"},
		Helpers(filters={"bold": lambda text: f"<b>{text}</b>"}),
	)

	html = views.render("index", {"title": "Hi"})

	assert_eq(html, "&lt;b&gt;Hi&lt;/b&gt;")


def test_renders_markup_helper_output_unescaped():
	views = Views(
		{"index": "{{ title | bold }}"},
		Helpers(filters={"bold": lambda text: Markup("<b>{}</b>").format(text)}),
	)

	html = views.render("index", {"title": "<i>"})

	assert_eq(html, "<b>&lt;i&gt;</b>")


def test_load_renders_application_helpers():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("{{ site }}")

		views = load(views_dir, Helpers(globals={"site": "Cork"}))

		assert_eq(views.render("index"), "Cork")


def test_load_ignores_hidden_files():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		views_dir.joinpath(".#index.html").write_bytes(b"\xff")

		views = load(views_dir)

		assert_eq(views.render("index"), "<h1>Index</h1>")


def test_load_ignores_hidden_directories():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		hidden_dir = views_dir.joinpath(".drafts")
		hidden_dir.mkdir()
		hidden_dir.joinpath("show.html").write_bytes(b"\xff")

		views = load(views_dir)

		assert_eq(views.render("index"), "<h1>Index</h1>")


def test_escapes_assigns():
	views = Views({"posts.index": "<h1>{{ title }}</h1>"})

	html = views.render("posts.index", {"title": "<script>alert(1)</script>"})

	assert_eq(html, "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>")


def test_escapes_assigns_in_loaded_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("{{ title }}")

		views = load(views_dir)

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
