from collections.abc import Callable

from helios.app import Context

from .view import View


class Composers:
	def __init__(self):
		self.items: list[Composer] = []

	def composer(self, composer: Composer):
		self.items.append(composer)

	def compose(self, view: View, context: Context):
		for composer in self.items:
			composer(view, context)


type Composer = Callable[[View, Context], None]
