from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs as parse_query
from urllib.parse import urlparse as parse_url
from wsgiref.types import StartResponse, WSGIEnvironment

from werkzeug.formparser import FormDataParser
from werkzeug.http import parse_options_header
from werkzeug.test import Client, Cookie, TestResponse
from werkzeug.wsgi import get_current_url

import helios.app
from helios.http import File, Files, Headers, Input, Method, Request, Response, URL


class Application(helios.app.Application):
	def __call__(
		self,
		env: WSGIEnvironment,
		start_res: StartResponse,
	) -> Iterable[bytes]:
		req = adapt_env(env)
		res = self.handle(req)
		return adapt_res(res, start_res)


def adapt_env(env: WSGIEnvironment) -> Request:
	input, files = adapt_input(env)
	return Request(
		adapt_method(env),
		adapt_url(env),
		adapt_headers(env),
		input,
		files,
	)


def adapt_res(res: Response, start_res: StartResponse) -> Iterable[bytes]:
	headers = list(res.headers)
	headers += list(res.cookies.to_headers())
	start_res(str(res.status), headers)
	return [res.body.to_bytes()]


def adapt_method(env: WSGIEnvironment) -> Method:
	raw = env["REQUEST_METHOD"]
	if raw == "GET":
		return Method.GET
	elif raw == "POST":
		return Method.POST
	elif raw == "PUT":
		return Method.PUT
	elif raw == "PATCH":
		return Method.PATCH
	elif raw == "DELETE":
		return Method.DELETE
	else:
		raise RuntimeError(f"Unsupported HTTP method '{raw}'")


def adapt_url(env: WSGIEnvironment) -> URL:
	raw = get_current_url(env)
	parsed = parse_url(raw)
	query = {}
	for name, vals in parse_query(parsed.query).items():
		if isinstance(vals, list) and len(vals) == 1:
			query[name] = vals[0]
		else:
			query[name] = vals
	return URL(parsed.path, query)


def adapt_headers(env: WSGIEnvironment) -> Headers:
	pairs = {}
	if "CONTENT_TYPE" in env:
		pairs["Content-Type"] = env["CONTENT_TYPE"]
	if "CONTENT_LENGTH" in env:
		pairs["Content-Length"] = env["CONTENT_LENGTH"]
	for raw_name in env:
		if raw_name.startswith("HTTP_"):
			name = raw_name.replace("HTTP_", "").replace("_", "-")
			pairs[name] = env[raw_name]
	return Headers(pairs)


def adapt_input(env: WSGIEnvironment) -> tuple[Input, Files]:
	if "CONTENT_TYPE" not in env:
		return Input(), Files()

	mime_type, _ = parse_options_header(env["CONTENT_TYPE"])
	if mime_type not in {
		"application/x-www-form-urlencoded",
		"multipart/form-data",
	}:
		return Input(), Files()

	_, form, uploads = FormDataParser().parse_from_environ(env)
	input_items: dict[str, str | list[str]] = {}
	for name, values in form.lists():
		input_items[name] = values[0] if len(values) == 1 else values

	file_items: dict[str, File | list[File]] = {}
	for name, storages in uploads.lists():
		files = [
			File(
				storage.read(),
				storage.filename or "",
				storage.content_type or "application/octet-stream",
			)
			for storage in storages
		]
		file_items[name] = files[0] if len(files) == 1 else files

	return Input(input_items), Files(file_items)


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
