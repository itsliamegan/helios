from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from werkzeug.test import Client, Cookie, TestResponse

from helios.app import Context
from helios.http import Headers, Method, Request
from helios.session import Session, Sessions
from helios.url import URL

from .application import Application


class TestClient:
	"""Sends requests to an application in tests, keeping cookies between them."""

	def __init__(self, app: Application):
		self.application = app
		self.client = Client(app, use_cookies=True)

	@contextmanager
	def session(self) -> Generator[Session]:
		"""Open the session that the client's next requests carry.

		The session is the one the client's cookie names, or a fresh one. After
		the block, a session with items is saved and the cookie set, and an
		emptied session is destroyed and the cookie deleted. When the block
		raises, nothing is saved.

		The block runs in a request context of its own. With the database
		driver, that context's transaction stays open until the block ends, so
		the block does not send requests through the client.
		"""

		headers = Headers()
		cookie = self.get_cookie("session_id")
		if cookie is not None:
			headers["Cookie"] = f"session_id={cookie.value}"
		request = Request(Method.GET, URL.parse("http://localhost/"), headers)

		with Context(self.application.container, request) as context:
			session = context.get(Session)
			yield session

			if session.items:
				context.get(Sessions).save(session)
				self.set_cookie("session_id", session.token)
			elif session.stored:
				context.get(Sessions).destroy(session)
				self.delete_cookie("session_id")

	def request(
		self,
		method: Method,
		path: str,
		query: Any = None,
		form: Any = None,
		headers: Any = None,
		redirect: bool = False,
		**kwargs: Any,
	) -> TestResponse:
		return self.client.open(
			path,
			method=method.value,
			query_string=query,
			data=form,
			headers=headers,
			follow_redirects=redirect,
			**kwargs,
		)

	def get(self, path: str, **kwargs: Any) -> TestResponse:
		return self.request(Method.GET, path, **kwargs)

	def post(self, path: str, **kwargs: Any) -> TestResponse:
		return self.request(Method.POST, path, **kwargs)

	def put(self, path: str, **kwargs: Any) -> TestResponse:
		return self.request(Method.PUT, path, **kwargs)

	def patch(self, path: str, **kwargs: Any) -> TestResponse:
		return self.request(Method.PATCH, path, **kwargs)

	def delete(self, path: str, **kwargs: Any) -> TestResponse:
		return self.request(Method.DELETE, path, **kwargs)

	def get_cookie(
		self,
		key: str,
		domain: str = "localhost",
		path: str = "/",
	) -> Cookie | None:
		return self.client.get_cookie(key, domain, path)

	def set_cookie(
		self,
		key: str,
		value: str = "",
		*,
		domain: str = "localhost",
		origin_only: bool = True,
		path: str = "/",
		**kwargs: Any,
	):
		self.client.set_cookie(
			key,
			value,
			domain=domain,
			origin_only=origin_only,
			path=path,
			**kwargs,
		)

	def delete_cookie(
		self,
		key: str,
		*,
		domain: str = "localhost",
		path: str = "/",
	):
		self.client.delete_cookie(key, domain=domain, path=path)
