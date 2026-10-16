from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.form import Errors, Submission
from helios.http import Input


def test_returns_submitted_values():
	submitted_tag_id = uuid4()
	saved_tag_id = uuid4()
	submission = Submission(
		Input({"title": "Intro", "tag_ids": [str(submitted_tag_id)]})
	)

	assert_eq(submission.value("title", "Old title"), "Intro")
	assert_eq(submission.value("tag_ids", [saved_tag_id]), [str(submitted_tag_id)])


def test_treats_fields_missing_from_submitted_input_as_empty():
	saved_tag_id = uuid4()
	submission = Submission(Input({"title": "Intro"}))

	assert_eq(submission.value("note", "Old note"), "")
	assert_eq(submission.value("open_in_new_tab", True), "")
	assert_eq(submission.value("tag_ids", [saved_tag_id]), [])


def test_shapes_submitted_values_by_default():
	tag_id = uuid4()
	submission = Submission(Input({"tag_ids": str(tag_id)}))

	assert_eq(submission.value("tag_ids", []), [str(tag_id)])
	assert_eq(submission.value("tag_ids"), str(tag_id))


def test_encodes_defaults_without_submitted_input():
	tag_id = uuid4()
	first_tag_id = uuid4()
	second_tag_id = uuid4()
	submission = Submission()

	assert_eq(submission.value("title"), "")
	assert_eq(submission.value("title", "Intro"), "Intro")
	assert_eq(submission.value("return_to", None), "")
	assert_eq(submission.value("open_in_new_tab", True), "on")
	assert_eq(submission.value("open_in_new_tab", False), "")
	assert_eq(submission.value("position", 3), "3")
	assert_eq(submission.value("tag_id", tag_id), str(tag_id))
	assert_eq(
		submission.value("tag_ids", (first_tag_id, second_tag_id)),
		[str(first_tag_id), str(second_tag_id)],
	)
	assert_eq(submission.value("flags", [True, False, None]), ["on", "", ""])


def test_reads_first_errors():
	submission = Submission(
		errors=Errors({"title": ["Title must be provided.", "That title is taken."]})
	)

	assert_eq(submission.error("title"), "Title must be provided.")
	assert_that(submission.invalid("title"))
	assert_eq(submission.error("note"), None)
	assert_that(not submission.invalid("note"))


def test_starts_empty():
	submission = Submission()

	assert_eq(submission.input, None)
	assert_eq(submission.errors, Errors())
	assert_that(not submission.invalid("title"))
