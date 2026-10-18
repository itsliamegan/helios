from dataclasses import dataclass
import logging
import sys


@dataclass(init=False)
class Logger:
	"""A logger that wraps the standard library implementation.

	Every message is prefixed with the logger's name when it has one. Every
	message is also prefixed with its level when it is a warning or an error.
	"""

	name: str | None
	wrapped: logging.Logger

	def __init__(self, name: str | None = None):
		self.name = name
		# Because logging.getLogger shares one logger per name, every Logger
		# would add another handler to it. A logger built directly is this
		# Logger's alone, and it has no parent to print its messages again.
		self.wrapped = logging.Logger(name or "")  # noqa: LOG001
		self.wrapped.addHandler(Handler(name))

	def info(self, message: str):
		self.wrapped.info(message)

	def warn(self, message: str):
		self.wrapped.warning(message)

	def error(self, message: str):
		self.wrapped.error(message)


class Handler(logging.Handler):
	"""A logging handler that writes each record to standard error with its level and an optional prefix."""

	def __init__(self, prefix: str | None):
		super().__init__()
		self.prefix = prefix

	def emit(self, record: logging.LogRecord):
		try:
			# Finding standard error on each write follows a redirection made
			# after the handler was created, such as the test runner's.
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
