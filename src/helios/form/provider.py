from helios.app import Application, Container, Context, Provider
from helios.flash import Flashes
from helios.http import Input
from helios.view import Engine, View

from .errors import Errors
from .submission import Submission
from .submissions import Submissions


class Provider(Provider):
	def register(self, container: Container):
		container.scoped(Submissions, self.submissions)
		container.scoped(Submission, self.submission)

	def boot(self, application: Application):
		if application.container.bound(Engine):
			application.container.get(Engine).composer(self.compose)

	def submissions(self, context: Context) -> Submissions:
		return Submissions(context.get(Flashes))

	def submission(self, context: Context) -> Submission:
		flash = context.get(Flashes)
		input = flash.get("_input")
		errors = flash.get("_errors")
		return Submission(
			Input(input) if input is not None else None,
			Errors(errors) if errors is not None else None,
		)

	def compose(self, view: View, context: Context):
		view.assign("submission", context.get(Submission))
