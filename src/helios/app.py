from collections.abc import Callable
from typing import Any

from helios.http import Method, Request, Response, Status
from helios.http.error import HTTPError
from helios.routing import Kernel, Next, Route

class Context:
	def __init__(self):
		self.provided = {}

	def __getattr__(self, name: str) -> Any:
		if name == "provided":
			return self.__dict__[name]
		elif name in self.provided:
			return self.provided[name]
		else:
			return super().__getattribute__(name)

	def __setattr__(self, name: str, val: Any):
		if name == "provided":
			self.__dict__[name] = val
		else:
			self.provided[name] = val

class Component:
	def boot(self):
		pass

	def before(self, req: Request, ctx: Context):
		pass

	def after(self, res: Response, ctx: Context):
		pass

	def __call__(self, req: Request, ctx: Context, next: Next) -> Response:
		self.before(req, ctx)
		res = next(req, ctx)
		self.after(res, ctx)
		return res

class Application:
	def __init__(self, routes: list[Route], components: list[Component]):
		self.kernel = Kernel(routes, [
			ensure_content_length,
			capture_errors,
			adapt_artificial_method,
			*components,
			handle_http_errors,
		])
		self.components = components

	def boot(self):
		for component in self.components:
			component.boot()

	def handle(self, req: Request) -> Response:
		ctx = Context()
		return self.kernel.handle(req, ctx)

def ensure_content_length(req: Request, ctx: Context, next: Next) -> Response:
	res = next(req, ctx)
	if "Content-Length" not in res.headers:
		res.headers["Content-Length"] = str(len(str(res.body)))
	return res

def adapt_artificial_method(req: Request, ctx: Context, next: Next) -> Response:
	if "_method" in req.input:
		raw_method = req.input["_method"]
		del req.input["_method"]
		if raw_method == "GET":
			method = Method.GET
		elif raw_method == "POST":
			method = Method.POST
		elif raw_method == "PUT":
			method = Method.PUT
		elif raw_method == "PATCH":
			method = Method.PATCH
		elif raw_method == "DELETE":
			method = Method.DELETE
		req.method = method
	return next(req, ctx)

def capture_errors(req: Request, ctx: Context, next: Next) -> Response:
	try:
		return next(req, ctx)
	except Exception as err:
		import sys
		import traceback
		traceback.print_exception(err, file = sys.stderr)
		return Response.text("500 Internal Server Error", Status.INTERNAL_SERVER_ERROR)

def handle_http_errors(req: Request, ctx: Context, next: Next) -> Response:
	try:
		return next(req, ctx)
	except HTTPError as err:
		return Response.text(f"{err.status}", err.status)
