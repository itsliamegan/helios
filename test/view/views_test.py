from luna.test.assertion import assert_eq

from helios.app import Container, Context
from helios.http import Method, Request, Status, URL
from helios.view import Engine, Views, memory


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


def context() -> Context:
	return Context(Container(), Request(Method.GET, URL("/")))
