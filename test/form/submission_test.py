from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.form import Errors, Submission
from helios.http import Input


def test_returns_submitted_values():
	submitted_board_id = uuid4()
	saved_board_id = uuid4()
	submission = Submission(
		Input({"title": "Intro", "board_ids": [str(submitted_board_id)]})
	)

	assert_eq(submission.value("title", "Old title"), "Intro")
	assert_eq(
		submission.value("board_ids", [saved_board_id]), [str(submitted_board_id)]
	)


def test_treats_fields_missing_from_submitted_input_as_empty():
	saved_board_id = uuid4()
	submission = Submission(Input({"title": "Intro"}))

	assert_eq(submission.value("note", "Old note"), "")
	assert_eq(submission.value("open_in_new_tab", True), "")
	assert_eq(submission.value("board_ids", [saved_board_id]), [])


def test_shapes_submitted_values_by_default():
	board_id = uuid4()
	submission = Submission(Input({"board_ids": str(board_id)}))

	assert_eq(submission.value("board_ids", []), [str(board_id)])
	assert_eq(submission.value("board_ids"), str(board_id))


def test_encodes_defaults_without_submitted_input():
	board_id = uuid4()
	first_board_id = uuid4()
	second_board_id = uuid4()
	submission = Submission()

	assert_eq(submission.value("title"), "")
	assert_eq(submission.value("title", "Intro"), "Intro")
	assert_eq(submission.value("return_to", None), "")
	assert_eq(submission.value("open_in_new_tab", True), "on")
	assert_eq(submission.value("open_in_new_tab", False), "")
	assert_eq(submission.value("position", 3), "3")
	assert_eq(submission.value("board_id", board_id), str(board_id))
	assert_eq(
		submission.value("board_ids", (first_board_id, second_board_id)),
		[str(first_board_id), str(second_board_id)],
	)
	assert_eq(submission.value("flags", [True, False, None]), ["on", "", ""])


def test_reads_first_errors():
	submission = Submission(
		errors=Errors({"title": ["Title must be provided.", "That title is taken."]})
	)

	assert_eq(submission.error("title"), "Title must be provided.")
	assert_that(submission.is_invalid("title"))
	assert_that(submission.error("note") is None)
	assert_that(not submission.is_invalid("note"))


def test_starts_empty():
	submission = Submission()

	assert_that(submission.input is None)
	assert_eq(submission.errors, Errors())
	assert_that(not submission.is_invalid("title"))
