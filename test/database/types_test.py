from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios import http
from helios.database import types


def test_round_trips_scalar_codecs():
	identifier = uuid4()
	url = http.URL("https://example.com/search?q=today")

	assert_eq(types.Str().decode(types.Str().encode("title")), "title")
	assert_eq(types.Int().decode(types.Int().encode(3)), 3)
	assert_eq(types.UUID().decode(types.UUID().encode(identifier)), identifier)
	assert_eq(str(types.URL().decode(types.URL().encode(url))), str(url))


def test_distinguishes_integers_and_booleans():
	assert_eq(types.Bool().encode(False), 0)
	assert_eq(types.Bool().encode(True), 1)
	assert_eq(types.Bool().decode(0), False)
	assert_eq(types.Bool().decode(1), True)

	with assert_raises(TypeError):
		types.Int().check(True)
	with assert_raises(TypeError):
		types.Int().decode(False)
	with assert_raises(TypeError):
		types.Bool().decode(2)
	with assert_raises(TypeError):
		types.Bool().decode(True)


def test_requires_canonical_uuid_text():
	identifier = uuid4()
	encoded = str(identifier)

	assert_eq(types.UUID().decode(encoded), identifier)
	with assert_raises(ValueError):
		types.UUID().decode(encoded.upper())
	with assert_raises(ValueError):
		types.UUID().decode(encoded.replace("-", ""))


def test_normalizes_datetimes_to_canonical_utc_text():
	value = datetime(2025, 2, 3, 4, 5, 6, 7, tzinfo=UTC) + timedelta(hours=2)
	encoded = types.Date().encode(value.astimezone(timezone(timedelta(hours=3))))

	assert_eq(encoded, "2025-02-03T06:05:06.000007Z")
	assert_eq(types.Date().decode(encoded), value)
	with assert_raises(TypeError):
		types.Date().encode(value.replace(tzinfo=None))
	with assert_raises(ValueError):
		types.Date().decode("2025-02-03T06:05:06Z")
	with assert_raises(ValueError):
		types.Date().decode("2025-02-03T06:05:06.000007+00:00")


def test_supports_custom_codec():
	class Uppercase:
		def check(self, value: object):
			if not isinstance(value, str):
				raise TypeError("expected a string")

		def encode(self, value: str):
			self.check(value)
			return value.upper()

		def decode(self, value: types.Scalar):
			if not isinstance(value, str):
				raise TypeError("expected a string")
			return value.lower()

	codec = Uppercase()
	encoded = types.encode(codec, "example")

	assert_eq(encoded, "EXAMPLE")
	assert_eq(codec.decode(encoded), "example")
	assert_that(isinstance(codec, types.Type))


def test_rejects_non_scalar_custom_encoding():
	class Invalid:
		def check(self, value: object):
			pass

		def encode(self, value: str):
			return [value]

		def decode(self, value: types.Scalar):
			return value

	with assert_raises(TypeError):
		types.encode(Invalid(), "secret")
