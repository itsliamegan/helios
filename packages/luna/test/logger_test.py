from contextlib import redirect_stderr
from io import StringIO

from luna.logger import Logger
from luna.test.assertion import assert_eq


def test_reports_information_with_its_name():
	logger = Logger("migrate")

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.info("applied 0042_add_tags")

	assert_eq(stderr.getvalue(), "migrate: applied 0042_add_tags\n")


def test_reports_a_warning_with_its_name():
	logger = Logger("migrate")

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.warn("0042_add_tags is already applied")

	assert_eq(stderr.getvalue(), "migrate: warning: 0042_add_tags is already applied\n")


def test_reports_an_error_with_its_name():
	logger = Logger("migrate")

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.error("0042_add_tags failed")

	assert_eq(stderr.getvalue(), "migrate: error: 0042_add_tags failed\n")


def test_reports_information_without_a_name():
	logger = Logger()

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.info("applied 0042_add_tags")

	assert_eq(stderr.getvalue(), "applied 0042_add_tags\n")


def test_reports_a_warning_without_a_name():
	logger = Logger()

	stderr = StringIO()
	with redirect_stderr(stderr):
		logger.warn("0042_add_tags is already applied")

	assert_eq(stderr.getvalue(), "warning: 0042_add_tags is already applied\n")
