from collections.abc import Iterator, Sequence
from typing import Self

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
		self.middlewares = Middlewares(middlewares)
		self.kernel: Kernel | None = None
		try:
			self.container.instance(Application, self)
			self.container.instance(Container, self.container)
			self.container.instance(Config, config)
			self.container.instance(Router, router)
			if config.base_url is not None:
				self.container.instance(URLs, URLs(router, config.base_url))

			for provider in self.providers:
				provider.register(self.container)
		except BaseException:
			self.container.close()
			raise

	def boot(self):
		if self.container.closed:
			raise RuntimeError("the application is closed")
		if self.kernel is not None:
			raise RuntimeError("the application is already booted")

		try:
			for provider in self.providers:
				provider.boot(self)
			self.kernel = Kernel(
				self.container,
				self.container.get(Router),
				list(self.middlewares),
			)
		except BaseException:
			self.container.close()
			raise

	def use(self, middleware: Middleware):
		# Providers add middleware to the application while booting, but the
		# kernel copies the list when it's built. Reject adding middleware that
		# would be added after this copy is made.
		if self.kernel is not None:
			raise RuntimeError("the application is already booted")

		self.middlewares.use(middleware)

	def handle(self, request: Request) -> Response:
		if self.container.closed:
			raise RuntimeError("the application is closed")
		if self.kernel is None:
			raise RuntimeError("the application is not booted")
		return self.kernel.handle(request)

	def close(self):
		self.container.close()

	def __enter__(self) -> Self:
		return self

	def __exit__(self, exception_type, exception, traceback):
		self.close()


class Middlewares:
	"""An application's middleware kept in two tiers.

	Those its providers use wrap those it was constructed with. Each tier keeps
	the order its middleware was added in.
	"""

	def __init__(self, middlewares: Sequence[Middleware]):
		self.provided: list[Middleware] = []
		self.application = list(middlewares)

	def __iter__(self) -> Iterator[Middleware]:
		yield from self.provided
		yield from self.application

	def use(self, middleware: Middleware):
		self.provided.append(middleware)
