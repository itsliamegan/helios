from luna.test.assertion import assert_eq

from helios.database.statement import Raw


def test_body_skips_leading_comments():
	statement = Raw("-- Posts.\n/* All of them. */\nSELECT * FROM posts;", ())

	assert_eq(statement.body, "SELECT * FROM posts;")


def test_body_of_an_unterminated_comment_is_empty():
	statement = Raw("/* SELECT * FROM posts;", ())

	assert_eq(statement.body, "")


def test_keyword_is_the_first_word_in_uppercase():
	statement = Raw("-- Posts.\ncommit;", ())

	assert_eq(statement.keyword, "COMMIT")


def test_keyword_of_an_empty_statement_is_empty():
	statement = Raw("-- Posts.\n", ())

	assert_eq(statement.keyword, "")


def test_summary_collapses_the_body_onto_one_line():
	statement = Raw("-- Posts.\nSELECT *\n\tFROM posts;", ())

	assert_eq(statement.summary, "SELECT * FROM posts;")


def test_summary_shortens_a_long_body():
	statement = Raw("SELECT " + "title, " * 20 + "id FROM posts;", ())

	assert_eq(len(statement.summary), 80)
