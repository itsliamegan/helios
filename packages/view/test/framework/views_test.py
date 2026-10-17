from jinja2 import UndefinedError
from luna.test.assertion import assert_eq, assert_raises

from helios.app import Container, Context
from helios.http import Method, Request, Status, URL
from helios.view import Component, Engine, memory
from helios.view.composer import Composers
from helios.view.views import Views


class Greeting(Component):
	template = "greeting"

	name: str


def test_views_render_html_responses():
	views = Views(
		Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"})),
		Composers(),
		context(),
	)

	response = views.render("index", {"title": "Index"})

	assert_eq(response.status, Status.OK)
	assert_eq(str(response.headers["Content-Type"]), "text/html")
	assert_eq(str(response.body), "<h1>Index</h1>")


def test_views_render_responses_with_status():
	views = Views(
		Engine(memory.Driver({"missing": "<h1>Not found</h1>"})),
		Composers(),
		context(),
	)

	response = views.render("missing", status=Status.NOT_FOUND)

	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(str(response.body), "<h1>Not found</h1>")


def test_views_render_shared_values():
	engine = Engine(memory.Driver({"index": "<h1>{{ title }}</h1>"}))
	composers = Composers()
	composers.composer(lambda view, context: view.share("title", "Composed"))
	views = Views(engine, composers, context())

	response = views.render("index")

	assert_eq(str(response.body), "<h1>Composed</h1>")


def test_views_pass_context_and_view_to_composers():
	engine = Engine(memory.Driver({"index": "{{ name }} {{ path }}"}))
	composers = Composers()
	composers.composer(lambda view, context: view.share("name", view.name))
	composers.composer(
		lambda view, context: view.share("path", str(context.request.url))
	)
	views = Views(engine, composers, context())

	response = views.render("index")

	assert_eq(str(response.body), "index /")


def test_views_run_composers_in_registration_order():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	composers = Composers()
	composers.composer(lambda view, context: view.share("title", "First"))
	composers.composer(lambda view, context: view.share("title", "Second"))
	views = Views(engine, composers, context())

	response = views.render("index")

	assert_eq(str(response.body), "Second")


def test_views_prefer_assigns_over_shared_values():
	engine = Engine(memory.Driver({"index": "{{ title }}"}))
	composers = Composers()
	composers.composer(lambda view, context: view.share("title", "Composed"))
	views = Views(engine, composers, context())

	response = views.render("index", {"title": "Assigned"})

	assert_eq(str(response.body), "Assigned")


def test_views_share_values_with_components():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Greeting(name="Hello") }}',
				"greeting": "{{ name }}, {{ user }}",
			}
		),
		components=[Greeting],
	)
	composers = Composers()
	composers.composer(lambda view, context: view.share("user", "Ada"))
	views = Views(engine, composers, context())

	response = views.render("index")

	assert_eq(str(response.body), "Hello, Ada")


def test_views_hide_assigns_from_components():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Greeting(name="Hello") }}',
				"greeting": "{{ name }}, {{ user }}",
			}
		),
		components=[Greeting],
	)
	views = Views(engine, Composers(), context())

	with assert_raises(UndefinedError):
		views.render("index", {"user": "Ada"})


def test_views_share_values_with_components_despite_assigns():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ user }} {{ Greeting(name="Hello") }}',
				"greeting": "{{ name }}, {{ user }}",
			}
		),
		components=[Greeting],
	)
	composers = Composers()
	composers.composer(lambda view, context: view.share("user", "Composed"))
	views = Views(engine, composers, context())

	response = views.render("index", {"user": "Assigned"})

	assert_eq(str(response.body), "Assigned Hello, Composed")


def context() -> Context:
	return Context(Container(), Request(Method.GET, URL("/")))
