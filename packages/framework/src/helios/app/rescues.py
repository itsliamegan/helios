from dataclasses import dataclass
from typing import cast

from helios.http import Response, Status
from helios.http.error import HTTPError


@dataclass(init=False)
class Rescues:
	"""Maps errors to the responses they render as.

	An `HTTPError` always renders with its own status. Any other error renders
	with the status registered for its type or for one of its base classes.
	An error that is not rescued renders as a server error.
	"""

	statuses: dict[type[Exception], Status]

	def __init__(self):
		self.statuses = {}

	def is_rescued(self, error: Exception) -> bool:
		return self.status_of(error) is not None

	def render(self, error: Exception) -> Response:
		status = self.status_of(error) or Status.INTERNAL_SERVER_ERROR
		return Response.text(f"{status}", status)

	def status_of(self, error: Exception) -> Status | None:
		if isinstance(error, HTTPError):
			return error.status

		for error_type in type(error).__mro__:
			if error_type in self.statuses:
				return self.statuses[cast(type[Exception], error_type)]
		return None
