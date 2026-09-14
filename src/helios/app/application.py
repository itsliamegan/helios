from helios.http import Request, Response, URL
from helios.routing import Router, URLs

from .container import Container
from .kernel import Kernel, Middleware


class Config:
	def __init__(self, base_url: URL | None = None):
		self.base_url = base_url


class Provider:
	def register(self, container: Container):
		pass

	def boot(self, application: Application):
		pass


class Application:
	def __init__(
		self,
		config: Config,
		router: Router,
		providers: list[Provider],
		middlewares: list[Middleware] | None = None,
	):
		self.container = Container()
		self.providers = list(providers)
		self.middlewares: list[Middleware] = []
		middlewares = middlewares or []
		try:
			for key, value in (
				(Application, self),
				(Container, self.container),
				(Config, config),
				(Router, router),
			):
				self.container.instance(key, value)
			if config.base_url is not None:
				self.container.instance(URLs, URLs(router, config.base_url))

			for provider in self.providers:
				provider.register(self.container)
			for provider in self.providers:
				provider.boot(self)
			self.middlewares.extend(middlewares)
			self.kernel = Kernel(self.container, router, self.middlewares)
		except BaseException:
			self.container.close()
			raise

	def use(self, middleware: Middleware):
		self.middlewares.append(middleware)

	def handle(self, request: Request) -> Response:
		return self.kernel.handle(request)

	def close(self):
		self.container.close()
