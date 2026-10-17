from datetime import UTC, datetime

from luna.test.assertion import assert_eq

from helios.view import helpers


def test_formats_date_with_default_format():
	date = datetime(year=2026, month=4, day=7, tzinfo=UTC)

	assert_eq(helpers.date(date), "Apr 7, 2026")


def test_formats_date_with_given_format():
	date = datetime(year=2026, month=4, day=7, tzinfo=UTC)

	assert_eq(helpers.date(date, "%B %-d, %Y"), "April 7, 2026")
