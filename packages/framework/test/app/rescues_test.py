from luna.test.assertion import assert_eq

from helios.app import Rescues
from helios.http import Status
from helios.http.error import NotFoundError


class ModerationError(Exception):
	pass


class SpamError(ModerationError):
	pass


def test_rescues_http_error_with_its_own_status():
	rescues = Rescues()

	response = rescues.render(NotFoundError())

	assert_eq(rescues.is_rescued(NotFoundError()), True)
	assert_eq(response.status, Status.NOT_FOUND)
	assert_eq(str(response.body), "404 Not Found")


def test_rescues_registered_error_with_its_status():
	rescues = Rescues()
	rescues.rescue(ModerationError, Status.FORBIDDEN)

	response = rescues.render(ModerationError())

	assert_eq(rescues.is_rescued(ModerationError()), True)
	assert_eq(response.status, Status.FORBIDDEN)


def test_rescues_subclass_of_registered_error():
	rescues = Rescues()
	rescues.rescue(ModerationError, Status.FORBIDDEN)

	assert_eq(rescues.is_rescued(SpamError()), True)
	assert_eq(rescues.render(SpamError()).status, Status.FORBIDDEN)


def test_prefers_status_registered_for_nearest_class():
	rescues = Rescues()
	rescues.rescue(ModerationError, Status.FORBIDDEN)
	rescues.rescue(SpamError, Status.BAD_REQUEST)

	assert_eq(rescues.render(SpamError()).status, Status.BAD_REQUEST)


def test_does_not_rescue_unregistered_error():
	rescues = Rescues()

	response = rescues.render(ModerationError())

	assert_eq(rescues.is_rescued(ModerationError()), False)
	assert_eq(response.status, Status.INTERNAL_SERVER_ERROR)
