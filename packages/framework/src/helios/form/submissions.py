from helios.http import Input
from helios.session import Flash

from .errors import Errors

ERRORS_KEY = "_errors"
INPUT_KEY = "_input"


class Submissions:
	def __init__(self, flash: Flash):
		self._flash = flash

	def flash(self, errors: Errors, input: Input | None = None):
		self._flash[ERRORS_KEY] = {
			name: list(messages) for name, messages in errors.messages.items()
		}
		if input is not None:
			self._flash[INPUT_KEY] = dict(input.items)
