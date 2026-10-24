from helios.app import Application, Container, Context, Provider
from helios.database import Model, Store
from helios.session.session import Session
from helios.session.sessions import Sessions
from helios.view import View
from helios.view.composer import Composers

from .authenticator import Authenticator


class Provider[U: Model](Provider):
	"""Provides each request's authentication service."""

	def __init__(self, user_type: type[U]):
		self.user_type = user_type

	def register(self, container: Container):
		container.scoped(Authenticator, self.authenticator)

	def boot(self, application: Application):
		if application.container.bound(Composers):
			application.container.get(Composers).add(self.compose)

	def compose(self, view: View, context: Context):
		view.share("auth", context.get(Authenticator))

	def authenticator(self, context: Context) -> Authenticator[U]:
		return Authenticator.read(
			context.get(Session),
			context.get(Sessions),
			context.get(Store),
			self.user_type,
		)
