from lux.app import Application, Component
from lux.http import Headers, Input, Method, Request, Response, Status, URL
from lux.routing import Pattern, Route

def test_boots_components():
	class ExampleComponent(Component):
		def boot(self):
			self.booted = True

	component = ExampleComponent()
	app = Application([], [component])

	app.boot()

	assert component.booted == True

def test_ensures_content_length():
	def index(req, ctx):
		return Response.text("Hello, world!")

	app = Application([Route(Method.GET, Pattern("/"), index)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert str(res.headers["Content-Length"]) == "13"

def test_adapts_artificial_method():
	def destroy(req, ctx):
		return Response.empty()

	app = Application([Route(Method.DELETE, Pattern("/"), destroy)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input({"_method": "DELETE"}))

	res = app.handle(req)

	assert res.status == Status.NO_CONTENT

def test_captures_errors():
	def index(req, ctx):
		raise RuntimeError

	app = Application([Route(Method.GET, Pattern("/"), index)], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.INTERNAL_SERVER_ERROR

def test_handles_not_found():
	app = Application([], [])
	req = Request(Method.GET, URL("/"), Headers(), Input())

	res = app.handle(req)

	assert res.status == Status.NOT_FOUND
