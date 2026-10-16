from .status import Status


class HTTPError(Exception):
	status: Status


class BadRequestError(HTTPError):
	status = Status.BAD_REQUEST


class NotFoundError(HTTPError):
	status = Status.NOT_FOUND


class ContentTooLargeError(HTTPError):
	status = Status.CONTENT_TOO_LARGE


class UnsupportedMethodError(HTTPError):
	status = Status.NOT_IMPLEMENTED
