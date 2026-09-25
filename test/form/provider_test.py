from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_that

from helios.app import Application, Config, Container, Provider
import helios.flash
import helios.form
from helios.form import Errors, Submission, Submissions
from helios.http import Input, Method, Request, Response, URL
from helios.routing import Pattern, Route, Router
from helios.session.store import Session
import helios.view
from helios.view import Views


class Values(Provider):
	def __init__(self, session: Session):
		self.session = session

	def register(self, container: Container):
		container.scoped(Session, lambda context: self.session)


def test_flashes_errors_and_input():
	session = Session(uuid4(), {})

	def update(request, context):
		context.get(Submissions).flash(
			Errors({"title": ["Title must be provided."]}), request.input
		)
		return Response.empty()

	handle(
		session,
		Route(Method.POST, Pattern("/"), update),
		Request(
			Method.POST,
			URL("/"),
			input=Input({"title": "", "board_ids": ["inbox", "later"]}),
		),
	)

	assert_eq(
		session["_flash"],
		{
			"_errors": {"title": ["Title must be provided."]},
			"_input": {"title": "", "board_ids": ["inbox", "later"]},
		},
	)


def test_flashes_errors_without_input():
	session = Session(uuid4(), {})

	def create(request, context):
		context.get(Submissions).flash(
			Errors({"recovery_code": ["That recovery code is invalid."]})
		)
		return Response.empty()

	handle(
		session,
		Route(Method.POST, Pattern("/"), create),
		Request(Method.POST, URL("/"), input=Input({"recovery_code": "secret"})),
	)

	assert_eq(
		session["_flash"],
		{"_errors": {"recovery_code": ["That recovery code is invalid."]}},
	)


def test_resolves_flashed_submission():
	session = Session(
		uuid4(),
		{
			"_flash": {
				"_errors": {"title": ["Title must be provided."]},
				"_input": {"title": ""},
			}
		},
	)
	submissions = []

	def edit(request, context):
		submissions.append(context.get(Submission))
		return Response.empty()

	handle(
		session, Route(Method.GET, Pattern("/"), edit), Request(Method.GET, URL("/"))
	)

	assert_eq(submissions[0].value("title", "Old title"), "")
	assert_eq(submissions[0].error("title"), "Title must be provided.")


def test_resolves_empty_submission_without_flashes():
	session = Session(uuid4(), {})
	submissions = []

	def edit(request, context):
		submissions.append(context.get(Submission))
		return Response.empty()

	handle(
		session, Route(Method.GET, Pattern("/"), edit), Request(Method.GET, URL("/"))
	)

	assert_that(submissions[0].input is None)
	assert_eq(submissions[0].value("title", "Old title"), "Old title")
	assert_that(not submissions[0].is_invalid("title"))


def test_shares_submission_with_views():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("edit.html").write_text(
			'{{ submission.value("title", "Old title") }}|'
			'{{ submission.error("title") }}|'
			'{{ submission.is_invalid("note") }}'
		)
		session = Session(
			uuid4(),
			{
				"_flash": {
					"_errors": {"title": ["Title must be provided."]},
					"_input": {"title": ""},
				}
			},
		)

		def edit(request, context):
			return context.get(Views).render("edit")

		response = handle(
			session,
			Route(Method.GET, Pattern("/"), edit),
			Request(Method.GET, URL("/")),
			[helios.view.Provider(helios.view.Config(views_dir))],
		)

	assert_eq(str(response.body), "|Title must be provided.|False")


def handle(session, route, request, providers=None):
	app = Application(
		Config(),
		Router([route]),
		[
			Values(session),
			helios.flash.Provider(),
			helios.form.Provider(),
			*(providers or []),
		],
	)
	try:
		return app.handle(request)
	finally:
		app.close()
