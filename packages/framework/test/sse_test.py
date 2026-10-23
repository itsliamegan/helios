from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.http import sse


def test_encodes_event_with_only_data():
	event = sse.Event("New post")

	assert_eq(event.encode(), b"data: New post\n\n")


def test_encodes_event_fields_in_order():
	event = sse.Event("New post", event="post", id="42")

	assert_eq(event.encode(), b"event: post\ndata: New post\nid: 42\n\n")


def test_splits_data_on_each_line_ending():
	assert_eq(sse.Event("Title\nBody").encode(), b"data: Title\ndata: Body\n\n")
	assert_eq(sse.Event("Title\rBody").encode(), b"data: Title\ndata: Body\n\n")
	assert_eq(sse.Event("Title\r\nBody").encode(), b"data: Title\ndata: Body\n\n")


def test_keeps_other_line_separators_in_data():
	event = sse.Event("Title Body")

	assert_eq(event.encode(), "data: Title Body\n\n".encode())


def test_encodes_empty_data_as_one_data_line():
	assert_eq(sse.Event("").encode(), b"data: \n\n")


def test_encodes_empty_id_as_field_without_value():
	event = sse.Event("New post", id="")

	assert_eq(event.encode(), b"data: New post\nid: \n\n")


def test_encodes_markup_data_unescaped():
	event = sse.Event(Markup("<article>New post</article>\n<p>By Ada</p>"))

	assert_eq(
		event.encode(), b"data: <article>New post</article>\ndata: <p>By Ada</p>\n\n"
	)


def test_encodes_non_ascii_data_as_utf8():
	event = sse.Event("Café opens")

	assert_eq(event.encode(), "data: Café opens\n\n".encode())


def test_encodes_comment():
	assert_eq(sse.Comment("heartbeat").encode(), b": heartbeat\n\n")


def test_rejects_newlines_in_event_types():
	with assert_raises(ValueError):
		sse.Event("New post", event="post\rcomment")
	with assert_raises(ValueError):
		sse.Event("New post", event="post\ncomment")


def test_rejects_newlines_and_nulls_in_event_ids():
	with assert_raises(ValueError):
		sse.Event("New post", id="42\r43")
	with assert_raises(ValueError):
		sse.Event("New post", id="42\n43")
	with assert_raises(ValueError):
		sse.Event("New post", id="42\x0043")


def test_rejects_newlines_in_comments():
	with assert_raises(ValueError):
		sse.Comment("heart\rbeat")
	with assert_raises(ValueError):
		sse.Comment("heart\nbeat")


def test_closes_source_when_encoding_is_closed_early():
	events = []

	def posts():
		try:
			yield sse.Event("First post")
			yield sse.Event("Second post")
		finally:
			events.append("closed")

	chunks = sse.encode(posts())
	assert_eq(next(chunks), b"data: First post\n\n")
	chunks.close()

	assert_eq(events, ["closed"])
