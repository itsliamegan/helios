from helios.flash import Flashes
from helios.http import Input

from .errors import Errors

ERRORS_KEY = "_errors"
INPUT_KEY = "_input"


class Submissions:
	def __init__(self, flashes: Flashes):
		self.flashes = flashes

	def flash(self, errors: Errors, input: Input | None = None):
		self.flashes[ERRORS_KEY] = {
			name: list(messages) for name, messages in errors.messages.items()
		}
		if input is not None:
			self.flashes[INPUT_KEY] = dict(input.items)
