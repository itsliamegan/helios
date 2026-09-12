from datetime import timedelta
from uuid import uuid4

from luna.test.assertion import assert_raises

from helios.app import Context
from helios.auth.state import Authenticator
from helios.data.model import Model, attr
from helios.data.store import Store
from helios.http import Headers, Input, Method, Request, Response, Status, URL
from helios.limit import RateLimitedError
from helios.limit.config import Config
from helios.limit.middleware import Middleware
from helios.session.store import Session


class User(Model):
	name = attr(str)


def context(signed_in: bool = False) -> Context:
	ctx = Context()
	session = Session(uuid4())
	if signed_in:
		store = Store()
		user = store.create(User, name="Alice")
		auth = Authenticator(session, user)
	else:
		auth = Authenticator(session)
	ctx.put(Authenticator, auth)
	return ctx


HEADER = "X-Forwarded-For"


def config(header: str = HEADER) -> Config:
	return Config(header=header, limit=1, window=timedelta(seconds=900))


def request(ip: str = "1.2.3.4") -> Request:
	return Request(Method.GET, URL("/"), Headers({HEADER: ip}), Input())


def ok(req: Request, ctx) -> Response:
	return Response.empty(Status.OK)


def test_limits_unauthenticated_requests():
	middleware = Middleware(config())
	middleware(request(), context(), ok)

	with assert_raises(RateLimitedError):
		middleware(request(), context(), ok)


def test_skips_authenticated_requests():
	middleware = Middleware(config())
	middleware(request(), context(), ok)

	middleware(request(), context(signed_in=True), ok)


def test_tracks_by_ip():
	middleware = Middleware(config())
	middleware(request("1.2.3.4"), context(), ok)

	middleware(request("5.6.7.8"), context(), ok)


def test_uses_configured_header():
	middleware = Middleware(config(header="X-Real-Ip"))
	req = Request(Method.GET, URL("/"), Headers({"X-Real-Ip": "1.2.3.4"}), Input())
	middleware(req, context(), ok)

	with assert_raises(RateLimitedError):
		req = Request(Method.GET, URL("/"), Headers({"X-Real-Ip": "1.2.3.4"}), Input())
		middleware(req, context(), ok)
