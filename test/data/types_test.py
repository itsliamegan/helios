from datetime import UTC, datetime
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_raises

from helios import http
from helios.data.types import Bool, Date, Int, Str, URL, UUID


def test_checks_canonical_values():
	assert_eq(Str().check("title"), None)
	assert_eq(Bool().check(True), None)
	assert_eq(Int().check(3), None)
	assert_eq(UUID().check(uuid4()), None)
	assert_eq(Date().check(datetime.now(UTC)), None)


def test_decodes_primitive_values():
	assert_eq(Str().decode("title"), "title")
	assert_eq(Bool().decode(True), True)
	assert_eq(Int().decode(3), 3)


def test_rejects_noncanonical_primitive_values():
	with assert_raises(TypeError):
		Str().check(3)
	with assert_raises(TypeError):
		Str().decode(3)
	with assert_raises(TypeError):
		Bool().check(1)
	with assert_raises(TypeError):
		Bool().decode(1)
	with assert_raises(TypeError):
		Int().check("3")
	with assert_raises(TypeError):
		Int().decode("3")
	with assert_raises(TypeError):
		Int().check(True)
	with assert_raises(TypeError):
		Int().decode(False)


def test_checks_and_decodes_uuid():
	value = uuid4()

	assert_eq(UUID().check(value), None)
	assert_eq(UUID().decode(str(value)), value)
	with assert_raises(TypeError):
		UUID().check(str(value))
	with assert_raises(TypeError):
		UUID().decode(value)
	with assert_raises(ValueError):
		UUID().decode("not-a-uuid")


def test_checks_and_decodes_url():
	value = http.URL("https://example.com:8443/search?q=today")

	assert_eq(URL().check(value), None)
	assert_eq(str(URL().decode(str(value))), str(value))
	with assert_raises(TypeError):
		URL().check(str(value))
	with assert_raises(TypeError):
		URL().decode(value)
	with assert_raises(ValueError):
		URL().decode("https://example.com:invalid")


def test_date_requires_aware_datetime():
	aware = datetime.now(UTC)
	naive = aware.replace(tzinfo=None)

	assert_eq(Date().check(aware), None)
	assert_eq(Date().decode(aware.isoformat()), aware)
	with assert_raises(TypeError):
		Date().check(naive)
	with assert_raises(TypeError):
		Date().check(aware.isoformat())
	with assert_raises(TypeError):
		Date().decode(aware)
	with assert_raises(ValueError):
		Date().decode("not-a-date")
	with assert_raises(ValueError):
		Date().decode(naive.isoformat())


def test_encodes_canonical_values():
	id = uuid4()
	date = datetime.now(UTC)

	assert_eq(Str().encode("title"), "title")
	assert_eq(Bool().encode(True), True)
	assert_eq(Int().encode(3), 3)
	assert_eq(UUID().encode(id), str(id))
	assert_eq(URL().encode(http.URL("/about")), "/about")
	assert_eq(Date().encode(date), date.isoformat())


def test_rejects_noncanonical_encoding():
	naive = datetime.now(UTC).replace(tzinfo=None)

	with assert_raises(TypeError):
		Str().encode(3)
	with assert_raises(TypeError):
		Bool().encode(1)
	with assert_raises(TypeError):
		Int().encode(True)
	with assert_raises(TypeError):
		UUID().encode(str(uuid4()))
	with assert_raises(TypeError):
		URL().encode("/about")
	with assert_raises(TypeError):
		Date().encode(naive)
