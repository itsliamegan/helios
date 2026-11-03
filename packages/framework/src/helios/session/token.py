import hashlib
import secrets
from typing import Self


class Token:
	"""A session token, identified by its SHA-256 digest.

	A token made from plaintext keeps the plaintext for the visitor's cookie. A
	token read back from storage has only its digest.
	"""

	def __init__(self, digest: str, plaintext: str | None = None):
		self.digest = digest
		self._plaintext = plaintext

	@classmethod
	def generate(cls) -> Self:
		return cls.from_plaintext(secrets.token_urlsafe(32))

	@classmethod
	def from_plaintext(cls, plaintext: str) -> Self:
		return cls(hashlib.sha256(plaintext.encode()).hexdigest(), plaintext)

	@property
	def plaintext(self) -> str:
		if self._plaintext is None:
			raise RuntimeError("the token has no plaintext")

		return self._plaintext

	def __eq__(self, other: object) -> bool:
		if isinstance(other, Token):
			return self.digest == other.digest
		else:
			return NotImplemented

	def __hash__(self) -> int:
		return hash(self.digest)

	def __repr__(self) -> str:
		return "Token(<redacted>)"
