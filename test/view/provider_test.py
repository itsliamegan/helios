from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq

from helios.app import Application, Config
from helios.http import Method, Request, URL
from helios.routing import Pattern, Route, Router
import helios.view
from helios.view import Views


def test_provider_shares_urls_with_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text(
			'<a href="{{ urls.route("boards.show", {"id": 7}) }}">Board</a>'
		)

		def index(request, context):
			return context.get(Views).render("index")

		app = Application(
			Config(URL("https://example.com")),
			Router(
				[
					Route(Method.GET, Pattern("/"), index),
					Route(
						Method.GET,
						Pattern("/boards/{id}"),
						index,
						name="boards.show",
					),
				]
			),
			[helios.view.Provider(helios.view.Config(views_dir))],
		)
		try:
			response = app.handle(Request(Method.GET, URL("/")))
		finally:
			app.close()

	assert_eq(str(response.body), '<a href="/boards/7">Board</a>')
