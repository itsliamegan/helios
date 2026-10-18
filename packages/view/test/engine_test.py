from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view import (
	Component,
	Engine,
	Helpers,
	TemplateError,
	View,
	file,
	memory,
)


def test_renders_simple():
	engine = Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"}))

	html = engine.render(View("index"), {"title": "Index"})

	assert_eq(html, "<h1>Index</h1>")


def test_renders_application_filters():
	engine = Engine(
		memory.Driver({"index": "{{ title | shout }}"}),
		Helpers(filters={"shout": lambda text: text.upper() + "!"}),
	)

	html = engine.render(View("index"), {"title": "hello"})

	assert_eq(html, "HELLO!")


def test_renders_application_globals():
	engine = Engine(
		memory.Driver({"index": "{{ greet(name) }} from {{ site }}"}),
		Helpers(globals={"greet": lambda name: f"Hi {name}", "site": "Cork"}),
	)

	html = engine.render(View("index"), {"name": "Ada"})

	assert_eq(html, "Hi Ada from Cork")


def test_keeps_default_filters_alongside_application_filters():
	engine = Engine(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"shout": lambda text: text.upper()}),
	)

	html = engine.render(View("index"), {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "Apr 7, 2026")


def test_date_filter_takes_an_optional_format():
	engine = Engine(
		memory.Driver({"index": '{{ day | date }} / {{ day | date("%B %-d, %Y") }}'}),
	)

	html = engine.render(View("index"), {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "Apr 7, 2026 / April 7, 2026")


def test_application_filters_override_defaults():
	engine = Engine(
		memory.Driver({"index": "{{ day | date }}"}),
		Helpers(filters={"date": lambda day: day.strftime("%Y-%m-%d")}),
	)

	html = engine.render(View("index"), {"day": datetime(2026, 4, 7, tzinfo=UTC)})

	assert_eq(html, "2026-04-07")


def test_escapes_plain_string_helper_output():
	engine = Engine(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: f"<b>{text}</b>"}),
	)

	html = engine.render(View("index"), {"title": "Hi"})

	assert_eq(html, "&lt;b&gt;Hi&lt;/b&gt;")


def test_renders_markup_helper_output_unescaped():
	engine = Engine(
		memory.Driver({"index": "{{ title | bold }}"}),
		Helpers(filters={"bold": lambda text: Markup("<b>{}</b>").format(text)}),
	)

	html = engine.render(View("index"), {"title": "<i>"})

	assert_eq(html, "<b>&lt;i&gt;</b>")


def test_escapes_assigns():
	engine = Engine(memory.Driver({"posts/index": "<h1>{{ title }}</h1>"}))

	html = engine.render(View("posts/index"), {"title": "<script>alert(1)</script>"})

	assert_eq(html, "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>")


def test_escapes_assigns_in_loaded_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		views_dir.joinpath("posts", "index.html").write_text("{{ title }}")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render(View("posts/index"), {"title": "<b>"}), "&lt;b&gt;")


def test_rejects_undefined_variables():
	engine = Engine(memory.Driver({"index": "<h1>{{ titel }}</h1>"}))

	with assert_raises(TemplateError):
		engine.render(View("index"), {"title": "Index"})


def test_rejects_undefined_attributes():
	engine = Engine(memory.Driver({"index": "<h1>{{ post.titel }}</h1>"}))

	with assert_raises(TemplateError):
		engine.render(View("index"), {"post": {"title": "Index"}})


def test_rejects_undefined_variables_in_conditions():
	engine = Engine(memory.Driver({"index": "{% if error %}{{ error }}{% endif %}"}))

	with assert_raises(TemplateError):
		engine.render(View("index"))


def test_renders_none_variables_in_conditions():
	engine = Engine(memory.Driver({"index": "{% if error %}{{ error }}{% endif %}"}))

	html = engine.render(View("index"), {"error": None})

	assert_eq(html, "")


def test_prints_nothing_as_empty():
	engine = Engine(memory.Driver({"index": "<p>{{ value }}</p>"}))

	html = engine.render(View("index"), {"value": None})

	assert_eq(html, "<p></p>")


def test_yields_nothing_to_or():
	engine = Engine(memory.Driver({"index": '{{ value or "fallback" }}'}))

	html = engine.render(View("index"), {"value": None})

	assert_eq(html, "fallback")


def test_nothing_equals_no_empty_string():
	engine = Engine(memory.Driver({"index": '{{ value == "" }}'}))

	html = engine.render(View("index"), {"value": None})

	assert_eq(html, "False")


def test_nothing_equals_no_word():
	engine = Engine(memory.Driver({"index": '{{ value == "None" }}'}))

	html = engine.render(View("index"), {"value": None})

	assert_eq(html, "False")


def test_rejects_members_of_nothing():
	engine = Engine(memory.Driver({"index": "{{ value.title }}"}))

	with assert_raises(TemplateError):
		engine.render(View("index"), {"value": None})


def test_rejects_looping_over_nothing():
	engine = Engine(
		memory.Driver({"index": "{% for item in value %}{{ item }}{% endfor %}"})
	)

	with assert_raises(TypeError):
		engine.render(View("index"), {"value": None})


def test_renders_shared_values():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))

	html = engine.render(View("index", {"title": "Shared"}))

	assert_eq(html, "Shared")


def test_prefers_assigns_over_shared_values():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))

	html = engine.render(View("index", {"title": "Shared"}), {"title": "Assigned"})

	assert_eq(html, "Assigned")


def test_renders_templates_only_a_fallback_has():
	engine = Engine(
		memory.Driver({"index": "own"}),
		fallbacks=[memory.Driver({"about": "fallback"})],
	)

	html = engine.render(View("about"))

	assert_eq(html, "fallback")


def test_prefers_own_templates_over_fallback_templates():
	engine = Engine(
		memory.Driver({"index": "own"}),
		fallbacks=[memory.Driver({"index": "fallback"})],
	)

	html = engine.render(View("index"))

	assert_eq(html, "own")


def test_tries_fallbacks_in_order():
	engine = Engine(
		memory.Driver({}),
		fallbacks=[
			memory.Driver({"index": "first"}),
			memory.Driver({"index": "second"}),
		],
	)

	html = engine.render(View("index"))

	assert_eq(html, "first")


def test_rejects_templates_no_driver_has_with_fallbacks():
	engine = Engine(
		memory.Driver({"index": "own"}),
		fallbacks=[memory.Driver({"about": "fallback"})],
	)

	with assert_raises(TemplateError):
		engine.render(View("missing"))


def test_registers_components_whose_templates_only_a_fallback_has():
	class Chip(Component):
		template = "chip"

	engine = Engine(
		memory.Driver({"index": "{{ Chip() }}"}),
		components=[Chip],
		fallbacks=[memory.Driver({"chip": "<i></i>"})],
	)

	html = engine.render(View("index"))

	assert_eq(html, "<i></i>")


def test_compiles_fallback_templates_when_made():
	with assert_raises(TemplateError):
		Engine(
			memory.Driver({"index": "own"}),
			fallbacks=[memory.Driver({"broken": "{% if %}"})],
		)


def test_wraps_runtime_errors_in_a_view():
	engine = Engine(memory.Driver({"posts/show": "<h1>Post</h1>\n{{ post.title }}"}))

	with assert_raises(TemplateError) as raised:
		engine.render(View("posts/show"))

	assert_eq(raised.exception.path, None)
	assert_eq(raised.exception.line, 2)


def test_passes_through_errors_raised_by_a_helper():
	def fail():
		raise ValueError("author")

	engine = Engine(
		memory.Driver({"posts/show": "{{ fail() }}"}),
		Helpers(globals={"fail": fail}),
	)

	with assert_raises(ValueError):
		engine.render(View("posts/show"))
