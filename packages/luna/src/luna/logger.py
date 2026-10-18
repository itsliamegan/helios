from dataclasses import dataclass
import logging
import sys


@dataclass(init=False)
class Logger:
	"""A logger that wraps the standard library implementation.

	Each message is written to standard error after its level, when it is a
	warning or an error, and after the logger's name, when it has one.
	"""

	name: str | None
	wrapped: logging.Logger

	def __init__(self, name: str | None = None):
		self.name = name
		# An unregistered logger has no parent, so it shares no handlers or
		# levels with any other logger.
		self.wrapped = logging.Logger(name or "")  # noqa: LOG001
		self.wrapped.addHandler(Handler(name))

	def info(self, message: str):
		self.wrapped.info(message)

	def warn(self, message: str):
		self.wrapped.warning(message)

	def error(self, message: str):
		self.wrapped.error(message)


class Handler(logging.Handler):
	"""Writes each record to standard error, labeled with its level and prefix.

	It finds standard error as it writes each record, so it follows a
	redirection made after it was created, such as the test runner's.
	"""

	def __init__(self, prefix: str | None):
		super().__init__()
		self.prefix = prefix

	def emit(self, record: logging.LogRecord):
		try:
			print(self.format(record), file=sys.stderr)
		except Exception:
			self.handleError(record)

	def format(self, record: logging.LogRecord) -> str:
		message = super().format(record)
		if record.levelno >= logging.ERROR:
			message = f"error: {message}"
		elif record.levelno >= logging.WARNING:
			message = f"warning: {message}"

		if self.prefix is None:
			return message
		else:
			return f"{self.prefix}: {message}"
