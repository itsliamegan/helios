from jinja2 import TemplateSyntaxError
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view import Component, Engine, memory


class Card(Component):
	template = "card"

	title: str
	content: Markup = Markup("<p>Empty</p>")


class Panel(Component):
	template = "panel"

	content: Markup


def test_fills_content_with_the_body():
	engine = Engine(
		memory.Driver(
			{
				"index": '{% render Card(title="Pins") %}<b>{{ name }}</b>{% endrender %}',
				"card": "<h2>{{ title }}</h2>{{ content }}",
			}
		),
		components=[Card],
	)

	html = engine.render("index", {"name": "<i>"})

	assert_eq(html, "<h2>Pins</h2><b>&lt;i&gt;</b>")


def test_renders_the_body_in_the_caller_scope():
	engine = Engine(
		memory.Driver(
			{
				"index": (
					"{% for pin in pins %}"
					"{% render Card(title=pin) %}{{ pin }} of {{ board }}{% endrender %}"
					"{% endfor %}"
				),
				"card": "[{{ content }}]",
			}
		),
		components=[Card],
	)

	html = engine.render("index", {"pins": ["a", "b"], "board": "Travel"})

	assert_eq(html, "[a of Travel][b of Travel]")


def test_uses_the_default_for_a_blank_body():
	engine = Engine(
		memory.Driver(
			{
				"index": '{% render Card(title="Pins") %}\n\t \n{% endrender %}',
				"card": "{{ content }}",
			}
		),
		components=[Card],
	)

	html = engine.render("index")

	assert_eq(html, "<p>Empty</p>")


def test_rejects_a_blank_body_for_required_content():
	engine = Engine(
		memory.Driver(
			{
				"index": "{% render Panel() %} {% endrender %}",
				"panel": "{{ content }}",
			}
		),
		components=[Panel],
	)

	with assert_raises(TypeError):
		engine.render("index")


def test_nests_render_inside_render():
	engine = Engine(
		memory.Driver(
			{
				"index": (
					"{% render Panel() %}"
					'{% render Card(title="Inner") %}<i>body</i>{% endrender %}'
					"{% endrender %}"
				),
				"panel": "<section>{{ content }}</section>",
				"card": "<h2>{{ title }}</h2>{{ content }}",
			}
		),
		components=[Card, Panel],
	)

	html = engine.render("index")

	assert_eq(html, "<section><h2>Inner</h2><i>body</i></section>")


def test_rejects_expressions_that_are_not_calls():
	driver = memory.Driver({"index": "{% render Card %}body{% endrender %}"})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_rejects_a_missing_endrender():
	driver = memory.Driver({"index": '{% render Card(title="a") %}body'})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)
