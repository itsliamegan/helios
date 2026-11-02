from datetime import UTC, datetime

from luna.test.assertion import assert_eq, assert_is, assert_not_none, assert_that

from helios.session.driver import memory
from helios.session.session import Session


def test_reads_a_written_session():
	driver = memory.Driver()
	last_active_at = datetime(2026, 10, 12, tzinfo=UTC)
	driver.write(Session("visitor-token", {"message": "Hello"}, last_active_at))

	session = assert_not_none(driver.read("visitor-token"))

	assert_eq(session.items, {"message": "Hello"})
	assert_eq(session.last_active_at, last_active_at)
	assert_that(session.stored)


def test_keeps_a_change_to_a_read_session_until_it_is_written():
	driver = memory.Driver()
	driver.write(Session("visitor-token", {"message": "Hello"}))
	session = assert_not_none(driver.read("visitor-token"))

	session["message"] = "Changed"

	assert_eq(assert_not_none(driver.read("visitor-token"))["message"], "Hello")


def test_destroying_an_unknown_token_succeeds():
	driver = memory.Driver()

	driver.destroy("unknown-token")

	assert_is(driver.read("unknown-token"), None)
