from helios.app import Application, Container, Context, Provider
from helios.http import Input
from helios.session import Flash
from helios.view import View
from helios.view.composer import Composers

from .errors import Errors
from .submission import Submission
from .submissions import ERRORS_KEY, INPUT_KEY, Submissions


class Provider(Provider):
	def register(self, container: Container):
		container.scoped(Submissions, self.submissions)
		container.scoped(Submission, self.submission)

	def boot(self, application: Application):
		if application.container.bound(Composers):
			application.container.get(Composers).add(self.compose)

	def submissions(self, context: Context) -> Submissions:
		return Submissions(context.get(Flash))

	def submission(self, context: Context) -> Submission:
		flash = context.get(Flash)
		input = flash.get(INPUT_KEY)
		errors = flash.get(ERRORS_KEY)
		return Submission(
			Input(input) if input is not None else None,
			Errors(errors) if errors is not None else None,
		)

	def compose(self, view: View, context: Context):
		view.share("submission", context.get(Submission))
