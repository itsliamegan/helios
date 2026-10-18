from dataclasses import dataclass
import logging
import sys


@dataclass
class Logger:
	"""Reports a program's status through a standard library logger."""

	logger: logging.Logger

	def info(self, message: str):
		self.logger.info(message)

	def warn(self, message: str):
		self.logger.warning(message)

	def error(self, message: str):
		self.logger.error(message)


class Handler(logging.Handler):
	"""Writes each record to standard error, prefixed with the program's name.

	It finds standard error as it writes each record, so it follows a
	redirection made after it was installed, such as the test runner's.
	"""

	def __init__(self, program: str):
		super().__init__()
		self.program = program

	def emit(self, record: logging.LogRecord):
		try:
			print(self.format(record), file=sys.stderr)
		except Exception:
			self.handleError(record)

	def format(self, record: logging.LogRecord) -> str:
		message = super().format(record)
		if record.levelno >= logging.ERROR:
			return f"{self.program}: error: {message}"
		elif record.levelno >= logging.WARNING:
			return f"{self.program}: warning: {message}"
		else:
			return f"{self.program}: {message}"
