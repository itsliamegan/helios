from jinja2 import (
	TemplateNotFound,
	TemplateRuntimeError,
	TemplateSyntaxError,
	UndefinedError,
)
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view import Component, Engine, View, memory


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
				"index": '{% render Card(title="Posts") %}<b>{{ name }}</b>{% endrender %}',
				"card": "<h2>{{ title }}</h2>{{ content }}",
			}
		),
		components=[Card],
	)

	html = engine.render(View("index"), {"name": "<i>"})

	assert_eq(html, "<h2>Posts</h2><b>&lt;i&gt;</b>")


def test_renders_the_body_in_the_caller_scope():
	engine = Engine(
		memory.Driver(
			{
				"index": (
					"{% for comment in comments %}"
					"{% render Card(title=comment) %}{{ comment }} on {{ post }}{% endrender %}"
					"{% endfor %}"
				),
				"card": "[{{ content }}]",
			}
		),
		components=[Card],
	)

	html = engine.render(View("index"), {"comments": ["a", "b"], "post": "Travel"})

	assert_eq(html, "[a on Travel][b on Travel]")


def test_uses_the_default_for_a_blank_body():
	engine = Engine(
		memory.Driver(
			{
				"index": '{% render Card(title="Posts") %}\n\t \n{% endrender %}',
				"card": "{{ content }}",
			}
		),
		components=[Card],
	)

	html = engine.render(View("index"))

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
		engine.render(View("index"))


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

	html = engine.render(View("index"))

	assert_eq(html, "<section><h2>Inner</h2><i>body</i></section>")


def test_rejects_expressions_that_are_not_calls():
	driver = memory.Driver({"index": "{% render Card %}body{% endrender %}"})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_rejects_a_missing_endrender():
	driver = memory.Driver({"index": '{% render Card(title="a") %}body'})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_renders_a_view_inside_its_layout():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "<main>{{ content }}</main>",
				"posts/show": '{% layout "layouts/base" %}<h1>{{ title }}</h1>',
			}
		)
	)

	html = engine.render(View("posts/show"), {"title": "<i>"})

	assert_eq(html, "<main><h1>&lt;i&gt;</h1></main>")


def test_passes_sections_to_the_layout():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "<title>{{ sections.title }}</title>{{ content }}",
				"posts/show": (
					'{% layout "layouts/base" %}'
					'{% section "title" %}<b>{{ title }}</b>{% endsection %}'
					"<p>Post</p>"
				),
			}
		)
	)

	html = engine.render(View("posts/show"), {"title": "<i>"})

	assert_eq(html, "<title><b>&lt;i&gt;</b></title><p>Post</p>")


def test_reads_sections_by_key():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": '{{ sections["title"] }}',
				"posts/show": (
					'{% layout "layouts/base" %}'
					'{% section "title" %}Post{% endsection %}'
				),
			}
		)
	)

	html = engine.render(View("posts/show"))

	assert_eq(html, "Post")


def test_reads_an_unset_section_as_nothing():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": '{{ sections.title or "Blog" }}',
				"posts/show": '{% layout "layouts/base" %}',
			}
		)
	)

	html = engine.render(View("posts/show"))

	assert_eq(html, "Blog")


def test_reads_an_empty_section_as_nothing():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": '{{ sections.title or "Blog" }}',
				"posts/show": (
					'{% layout "layouts/base" %}'
					'{% section "title" %}\n\t {% endsection %}'
				),
			}
		)
	)

	html = engine.render(View("posts/show"))

	assert_eq(html, "Blog")


def test_lets_a_layout_set_sections_for_its_own_layout():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": (
					"<title>{{ sections.title }}</title>"
					"<nav>{{ sections.nav }}</nav>"
					"{{ content }}"
				),
				"layouts/app": (
					'{% layout "layouts/base" %}'
					'{% section "nav" %}Posts{% endsection %}'
					"<main>{{ content }}</main>"
				),
				"posts/show": (
					'{% layout "layouts/app" %}'
					'{% section "title" %}Post{% endsection %}'
					"<p>Post</p>"
				),
			}
		)
	)

	html = engine.render(View("posts/show"))

	assert_eq(
		html,
		"<title>Post</title><nav>Posts</nav><main><p>Post</p></main>",
	)


def test_shows_the_layout_the_context_the_view_was_rendered_with():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "{{ author }} {{ title }} {{ content }}",
				"posts/show": '{% layout "layouts/base" %}post',
			}
		)
	)

	html = engine.render(View("posts/show", {"author": "Ada"}), {"title": "Intro"})

	assert_eq(html, "Ada Intro post")


def test_hides_the_view_assignments_from_the_layout():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "{{ tag }}",
				"posts/show": '{% layout "layouts/base" %}{% set tag = "travel" %}',
			}
		)
	)

	with assert_raises(UndefinedError):
		engine.render(View("posts/show"))


def test_rejects_a_section_set_twice_in_one_view():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "{{ sections.title }}",
				"posts/show": (
					'{% layout "layouts/base" %}'
					'{% section "title" %}a{% endsection %}'
					'{% section "title" %}b{% endsection %}'
				),
			}
		)
	)

	with assert_raises(TemplateRuntimeError):
		engine.render(View("posts/show"))


def test_rejects_a_layout_setting_a_section_its_view_set():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "{{ sections.title }}",
				"layouts/app": (
					'{% layout "layouts/base" %}'
					'{% section "title" %}Blog{% endsection %}'
				),
				"posts/show": (
					'{% layout "layouts/app" %}'
					'{% section "title" %}Post{% endsection %}'
				),
			}
		)
	)

	with assert_raises(TemplateRuntimeError):
		engine.render(View("posts/show"))


def test_rejects_a_second_layout():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": "{{ content }}",
				"layouts/app": "{{ content }}",
				"posts/show": '{% layout "layouts/base" %}{% layout "layouts/app" %}',
			}
		)
	)

	with assert_raises(TemplateRuntimeError):
		engine.render(View("posts/show"))


def test_rejects_a_missing_layout():
	engine = Engine(memory.Driver({"posts/show": '{% layout "layouts/base" %}'}))

	with assert_raises(TemplateNotFound):
		engine.render(View("posts/show"))


def test_rejects_a_loop_of_layouts():
	engine = Engine(
		memory.Driver(
			{
				"layouts/base": '{% layout "layouts/app" %}{{ content }}',
				"layouts/app": '{% layout "layouts/base" %}{{ content }}',
				"posts/show": '{% layout "layouts/app" %}',
			}
		)
	)

	with assert_raises(TemplateRuntimeError):
		engine.render(View("posts/show"))


def test_rejects_a_layout_name_that_is_not_a_literal():
	driver = memory.Driver({"posts/show": "{% layout name %}"})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_rejects_a_section_name_that_is_not_a_literal():
	driver = memory.Driver({"posts/show": "{% section name %}a{% endsection %}"})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_rejects_a_missing_endsection():
	driver = memory.Driver({"posts/show": '{% section "title" %}a'})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_disables_extends():
	driver = memory.Driver(
		{
			"layouts/base": "{{ content }}",
			"posts/show": '{% extends "layouts/base" %}',
		}
	)

	with assert_raises(TemplateSyntaxError):
		Engine(driver)


def test_disables_block():
	driver = memory.Driver({"posts/show": "{% block title %}{% endblock %}"})

	with assert_raises(TemplateSyntaxError):
		Engine(driver)
