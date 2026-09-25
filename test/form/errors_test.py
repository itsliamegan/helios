from luna.test.assertion import assert_eq, assert_that

from helios.form import Errors


def test_starts_empty():
	errors = Errors()

	assert_that(not errors)
	assert_that("title" not in errors)
	assert_eq(errors.first("title"), None)
	assert_eq(errors["title"], [])


def test_adds_messages_in_order():
	errors = Errors()

	errors.add("title", "Title must be provided.")
	errors.add("title", "That title is taken.")

	assert_that(errors)
	assert_that("title" in errors)
	assert_eq(errors.first("title"), "Title must be provided.")
	assert_eq(errors["title"], ["Title must be provided.", "That title is taken."])


def test_copies_initial_messages():
	messages = {"title": ["Title must be provided."]}
	errors = Errors(messages)

	errors.add("title", "That title is taken.")

	assert_eq(messages, {"title": ["Title must be provided."]})
	assert_eq(errors.messages["title"][1], "That title is taken.")
