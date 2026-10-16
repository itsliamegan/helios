from enum import Enum


class Escape(Enum):
	RED = "\033[31m"
	GREEN = "\033[32m"
	YELLOW = "\033[33m"
	RESET = "\033[0m"

	def __init__(self, escape: str):
		self.escape = escape

	def __str__(self) -> str:
		return self.escape


def escape(code: Escape, text: str) -> str:
	return f"{code}{text}{Escape.RESET}"
