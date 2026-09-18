from typing import Any

from werkzeug.test import Client, Cookie, TestResponse

from helios.http import Method

from .application import Application


class TestClient:
	def __init__(self, app: Application):
		self.client = Client(app, use_cookies=True)

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
