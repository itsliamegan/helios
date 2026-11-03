from helios.database.codec import Codec, Scalar

from ...token import Token


class Codec(Codec):
	"""Stores a session token as its digest."""

	converts = Token

	def encode(self, value: Token) -> Scalar:
		return value.digest

	def decode(self, value: Scalar) -> Token:
		if not isinstance(value, str):
			raise TypeError(f"expected a string, got {type(value).__name__}")
		return Token(value)
