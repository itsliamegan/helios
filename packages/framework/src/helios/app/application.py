from abc import ABC
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from helios.http import Request, Response
from helios.routing import Router, URLs
from helios.url import URL

from .container import Container
from .kernel import Kernel
from .middleware import Middleware, Middlewares
from .rescues import Rescues


class Application:
	"""Coordinates services, providers, and middleware.

	Constructing an application registers its providers. Booting an application
	boots providers and builds the HTTP kernel. Once booted, the application can
	handle HTTP requests and cannot change its middleware stack. Closing the
	application releases its services.
	"""

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
		self.rescues = Rescues()
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
				self.middlewares,
				self.rescues,
			)
		except BaseException:
			self.container.close()
			raise

	def use(self, middleware: Middleware):
		# Providers add middleware to the application while booting, but the
		# kernel builds its chain from the middleware once. Reject adding
		# middleware that would be added after the chain is built.
		if self.kernel is not None:
			raise RuntimeError("the application is already booted")

		self.middlewares.provide(middleware)

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


class Provider(ABC):
	"""Adds services and behavior to an application.

	Every provider registers its bindings before any provider boots. Booting
	can resolve other providers' services and add middleware.
	"""

	def register(self, container: Container): ...

	def boot(self, application: Application): ...


@dataclass
class Config:
	base_url: URL | None = None
