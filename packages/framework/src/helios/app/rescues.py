from dataclasses import dataclass
from typing import cast

from helios.http import Response, Status
from helios.http.error import HTTPError


@dataclass(init=False)
class Rescues:
	"""Maps errors encountered in handlers to responses.

	An `HTTPError` always renders with its own status. Any other error renders
	with the status registered for its type or for one of its base classes.
	An error that is not rescued renders as a server error.
	"""

	statuses: dict[type[Exception], Status]

	def __init__(self):
		self.statuses = {}

	def render(self, error: Exception) -> Response:
		status = self.status(error) or Status.INTERNAL_SERVER_ERROR
		return Response.text(f"{status}", status)

	def rescue(self, error_type: type[Exception], status: Status):
		self.statuses[error_type] = status

	def is_rescued(self, error: Exception) -> bool:
		return self.status(error) is not None

	def status(self, error: Exception) -> Status | None:
		if isinstance(error, HTTPError):
			return error.status

		# Ensure that a subclass of a rescued error is mapped to the superclass'
		# status. Walk the error's ancestor chain rather than checking against
		# each rescued error so that the check takes linear time in terms of the
		# number of superclasses rather than the number of rescued errors.
		for error_type in type(error).__mro__:
			if error_type in self.statuses:
				return self.statuses[cast(type[Exception], error_type)]
		return None
