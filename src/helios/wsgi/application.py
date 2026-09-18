from collections.abc import Iterable
from wsgiref.types import StartResponse, WSGIEnvironment

import helios.app

from .adapt import RequestAdapter, ResponseAdapter


class Application(helios.app.Application):
	def __call__(
		self,
		environment: WSGIEnvironment,
		start_response: StartResponse,
	) -> Iterable[bytes]:
		response = self.handle(RequestAdapter(environment).adapt())
		return ResponseAdapter(response, start_response).adapt()
