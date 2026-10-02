from collections.abc import Iterable
from wsgiref.types import StartResponse, WSGIEnvironment

import helios.app
from helios.http import Response
from helios.http.error import HTTPError

from .adapt import RequestAdapter, ResponseAdapter


class Application(helios.app.Application):
	def __call__(
		self,
		environment: WSGIEnvironment,
		start_response: StartResponse,
	) -> Iterable[bytes]:
		try:
			request = RequestAdapter(environment).adapt()
		except HTTPError as error:
			response = Response.error(error)
		else:
			response = self.handle(request)
		return ResponseAdapter(response, start_response).adapt()
