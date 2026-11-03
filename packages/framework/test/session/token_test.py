import hashlib

from luna.test.assertion import assert_eq, assert_raises

from helios.session.token import Token


def test_generated_token_is_identified_by_the_digest_of_its_plaintext():
	token = Token.generate()

	assert_eq(token.digest, hashlib.sha256(token.plaintext.encode()).hexdigest())


def test_token_from_a_digest_has_no_plaintext():
	token = Token(hashlib.sha256(b"visitor-token").hexdigest())

	with assert_raises(RuntimeError):
		_ = token.plaintext


def test_tokens_with_the_same_digest_are_equal():
	token = Token.from_plaintext("visitor-token")

	assert_eq(Token(token.digest), token)
