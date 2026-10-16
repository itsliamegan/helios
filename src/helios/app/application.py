from collections.abc import Sequence

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
		providers: Sequence[Provider],
		middlewares: Sequence[Middleware] | None = None,
	):
		middlewares = middlewares or []

		self.container = Container()
		self.providers = list(providers)
		self.middlewares = list(middlewares)
		self.used: list[Middleware] = []
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
		except BaseException:
			self.container.close()
			raise

	def boot(self):
		try:
			for provider in self.providers:
				provider.boot(self)
			self.kernel = Kernel(
				self.container,
				self.container.get(Router),
				self.used + self.middlewares,
			)
		except BaseException:
			self.container.close()
			raise

	def use(self, middleware: Middleware):
		self.used.append(middleware)

	def handle(self, request: Request) -> Response:
		return self.kernel.handle(request)

	def close(self):
		self.container.close()
