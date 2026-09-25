from uuid import UUID

from luna.test.assertion import assert_eq, assert_that

from helios.form import Errors, Submission
from helios.http import Input

FIRST_ID = "102ddad7-06d1-484f-a3f8-3cf4711e91ba"
SECOND_ID = "f262c72c-92e8-4e1f-9644-b1d24afad614"


def test_returns_submitted_values():
	submission = Submission(Input({"title": "Intro", "board_ids": [FIRST_ID]}))

	assert_eq(submission.value("title", "Old title"), "Intro")
	assert_eq(submission.value("board_ids", [UUID(SECOND_ID)]), [FIRST_ID])


def test_treats_fields_missing_from_submitted_input_as_empty():
	submission = Submission(Input({"title": "Intro"}))

	assert_eq(submission.value("note", "Old note"), "")
	assert_eq(submission.value("open_in_new_tab", True), "")
	assert_eq(submission.value("board_ids", [UUID(FIRST_ID)]), [])


def test_shapes_submitted_values_by_default():
	submission = Submission(Input({"board_ids": FIRST_ID}))

	assert_eq(submission.value("board_ids", []), [FIRST_ID])
	assert_eq(submission.value("board_ids"), FIRST_ID)


def test_encodes_defaults_without_submitted_input():
	submission = Submission()

	assert_eq(submission.value("title"), "")
	assert_eq(submission.value("title", "Intro"), "Intro")
	assert_eq(submission.value("return_to", None), "")
	assert_eq(submission.value("open_in_new_tab", True), "on")
	assert_eq(submission.value("open_in_new_tab", False), "")
	assert_eq(submission.value("position", 3), "3")
	assert_eq(submission.value("board_id", UUID(FIRST_ID)), FIRST_ID)
	assert_eq(
		submission.value("board_ids", (UUID(FIRST_ID), UUID(SECOND_ID))),
		[FIRST_ID, SECOND_ID],
	)
	assert_eq(submission.value("flags", [True, False, None]), ["on", "", ""])


def test_reads_first_errors():
	submission = Submission(
		errors=Errors({"title": ["Title must be provided.", "That title is taken."]})
	)

	assert_eq(submission.error("title"), "Title must be provided.")
	assert_that(submission.invalid("title"))
	assert_that(submission.error("note") is None)
	assert_that(not submission.invalid("note"))


def test_starts_empty():
	submission = Submission()

	assert_that(submission.input is None)
	assert_eq(submission.errors, Errors())
	assert_that(not submission.invalid("title"))
