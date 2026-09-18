from datetime import timedelta
from pathlib import Path

from luna.test.assertion import assert_eq, assert_raises

from helios.database import Config


def test_defaults_busy_timeout():
	config = Config(Path("app.sqlite"))

	assert_eq(config.busy_timeout, timedelta(seconds=30))
	assert_eq(config.busy_timeout_milliseconds, 30_000)


def test_rejects_negative_busy_timeout():
	with assert_raises(ValueError):
		Config(Path("app.sqlite"), timedelta(microseconds=-1))
