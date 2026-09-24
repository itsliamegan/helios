from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import assert_eq

from helios.app import Application, Config, Container, Provider
import helios.flash
from helios.flash import Flashes
from helios.http import Method, Request, Response, URL
from helios.routing import Pattern, Route, Router
from helios.session.store import Session
import helios.view
from helios.view import Views


class Values(Provider):
	def __init__(self, session: Session):
		self.session = session

	def register(self, container: Container):
		container.scoped(Session, lambda context: self.session)


def test_gets_flash_value():
	flashes = Flashes({"notice": "Saved"})

	assert_eq(flashes.get("notice"), "Saved")


def test_gets_default_for_missing_flash():
	flashes = Flashes()

	assert_eq(
		[flashes.get("notice"), flashes.get("notice", "None yet")], [None, "None yet"]
	)


def test_shares_flash_with_views():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text('{{ flash.get("notice") }}')
		session = Session(uuid4(), {"_flash": {"notice": "Saved"}})

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			Config(),
			Router([Route(Method.GET, Pattern("/"), index)]),
			[
				Values(session),
				helios.flash.Provider(),
				helios.view.Provider(helios.view.Config(views_dir)),
			],
		)
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(str(response.body), "Saved")


def test_boots_without_views():
	session = Session(uuid4(), {"_flash": {"notice": "Saved"}})
	notices = []

	def index(request, context):
		notices.append(context.get(Flashes).get("notice"))
		return Response.empty()

	app = Application(
		Config(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[Values(session), helios.flash.Provider()],
	)
	try:
		app.handle(Request(Method.GET, URL("/")))
	finally:
		app.close()

	assert_eq(notices, ["Saved"])
