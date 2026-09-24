from .status import Status


class HTTPError(Exception):
	status: Status


class NotFoundError(HTTPError):
	status = Status.NOT_FOUND
