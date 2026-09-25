from helios.flash import Flashes
from helios.http import Input

from .errors import Errors


class Submissions:
	def __init__(self, flashes: Flashes):
		self.flashes = flashes

	def flash(self, errors: Errors, input: Input | None = None):
		self.flashes["_errors"] = {
			name: list(messages) for name, messages in errors.messages.items()
		}
		if input is not None:
			self.flashes["_input"] = dict(input.items)
