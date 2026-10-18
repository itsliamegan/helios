from contextlib import redirect_stderr
from io import StringIO
import logging

from luna.logger import Handler, Logger
from luna.test.assertion import assert_eq


def test_reports_information_with_the_program_name():
	standard = logging.Logger("migrations")  # noqa: LOG001
	standard.addHandler(Handler("migrate"))
	logger = Logger(standard)

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.info("applied 0042_add_tags")

	assert_eq(stderr.getvalue(), "migrate: applied 0042_add_tags\n")


def test_reports_a_warning_with_the_program_name():
	standard = logging.Logger("migrations")  # noqa: LOG001
	standard.addHandler(Handler("migrate"))
	logger = Logger(standard)

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.warn("0042_add_tags is already applied")

	assert_eq(stderr.getvalue(), "migrate: warning: 0042_add_tags is already applied\n")


def test_reports_an_error_with_the_program_name():
	standard = logging.Logger("migrations")  # noqa: LOG001
	standard.addHandler(Handler("migrate"))
	logger = Logger(standard)

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.error("0042_add_tags failed")

	assert_eq(stderr.getvalue(), "migrate: error: 0042_add_tags failed\n")
