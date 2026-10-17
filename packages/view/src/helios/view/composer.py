from collections.abc import Callable

from helios.app import Context

from .view import View


class Composers:
	def __init__(self):
		self.composers: list[Composer] = []

	def add(self, composer: Composer):
		self.composers.append(composer)

	def compose(self, view: View, context: Context):
		for composer in self.composers:
			composer(view, context)


type Composer = Callable[[View, Context], None]
