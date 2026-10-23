from .status import Status


class HTTPError(Exception):
	"""An error that renders as a response with its `status`."""

	status: Status


class BadRequestError(HTTPError):
	status = Status.BAD_REQUEST


class NotFoundError(HTTPError):
	status = Status.NOT_FOUND


class ContentTooLargeError(HTTPError):
	status = Status.CONTENT_TOO_LARGE


class InternalServerError(HTTPError):
	status = Status.INTERNAL_SERVER_ERROR


class UnsupportedMethodError(HTTPError):
	"""Raised for an HTTP method that the *framework* does not support.

	Its status is 501 rather than 405, because a 405 means a resource does not
	allow a method the server supports, and it must list the allowed methods
	in an `Allow` header.
	"""

	status = Status.NOT_IMPLEMENTED
