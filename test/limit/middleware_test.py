from datetime import timedelta
from uuid import uuid4

from luna.test.assertion import assert_eq

from helios.app import Application, Container, Provider
from helios.app import Config as AppConfig
from helios.auth.state import Authenticator
from helios.database import Model, attr
from helios.http import Headers, Method, Request, Response, Status, URL
import helios.limit
from helios.limit.config import Config
from helios.routing import Pattern, Route, Router
from helios.session.store import Session


class User(Model):
	table = "users"

	name = attr(str)


class Authentication(Provider):
	def __init__(self, signed_in: bool):
		self.signed_in = signed_in

	def register(self, container: Container):
		container.scoped(Authenticator, self.authenticator)

	def authenticator(self, context):
		session = Session(uuid4())
		if self.signed_in:
			return Authenticator(session, User(name="Alice"))
		return Authenticator(session)


HEADER = "X-Forwarded-For"


def config(header: str = HEADER) -> Config:
	return Config(header=header, limit=1, window=timedelta(seconds=900))


def request(ip: str = "1.2.3.4", header: str = HEADER) -> Request:
	return Request(Method.GET, URL("/"), Headers({header: ip}))


def application(signed_in: bool = False, limit_config: Config | None = None):
	def index(request, context):
		return Response.empty(Status.OK)

	return Application(
		AppConfig(),
		Router([Route(Method.GET, Pattern("/"), index)]),
		[Authentication(signed_in)],
		[helios.limit.Middleware(limit_config or config())],
	)


def test_limits_unauthenticated_requests():
	app = application()

	assert_eq(app.handle(request()).status, Status.OK)
	assert_eq(app.handle(request()).status, Status.TOO_MANY_REQUESTS)


def test_skips_authenticated_requests():
	app = application(signed_in=True)

	assert_eq(app.handle(request()).status, Status.OK)
	assert_eq(app.handle(request()).status, Status.OK)


def test_tracks_by_ip():
	app = application()

	assert_eq(app.handle(request("1.2.3.4")).status, Status.OK)
	assert_eq(app.handle(request("5.6.7.8")).status, Status.OK)


def test_uses_configured_header():
	app = application(limit_config=config(header="X-Real-Ip"))

	assert_eq(app.handle(request(header="X-Real-Ip")).status, Status.OK)
	assert_eq(
		app.handle(request(header="X-Real-Ip")).status,
		Status.TOO_MANY_REQUESTS,
	)
