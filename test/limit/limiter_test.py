from datetime import timedelta

from luna.test.assertion import assert_raises
import time_machine

from helios.limit import RateLimitedError, RateLimiter


def test_allows_requests_within_limit():
	limiter = RateLimiter(3, timedelta(seconds=900))

	limiter.hit("1.2.3.4")
	limiter.hit("1.2.3.4")
	limiter.hit("1.2.3.4")


def test_rejects_requests_over_limit():
	limiter = RateLimiter(3, timedelta(seconds=900))
	limiter.hit("1.2.3.4")
	limiter.hit("1.2.3.4")
	limiter.hit("1.2.3.4")

	with assert_raises(RateLimitedError):
		limiter.hit("1.2.3.4")


def test_tracks_keys_independently():
	limiter = RateLimiter(1, timedelta(seconds=900))
	limiter.hit("1.2.3.4")

	limiter.hit("5.6.7.8")


def test_resets_after_window():
	limiter = RateLimiter(1, timedelta(seconds=60))

	with time_machine.travel(0, tick=False) as t:
		limiter.hit("1.2.3.4")

		t.shift(timedelta(seconds=60))

		limiter.hit("1.2.3.4")


def test_does_not_reset_before_window():
	limiter = RateLimiter(1, timedelta(seconds=60))

	with time_machine.travel(0, tick=False) as t:
		limiter.hit("1.2.3.4")

		t.shift(timedelta(seconds=59))

		with assert_raises(RateLimitedError):
			limiter.hit("1.2.3.4")
