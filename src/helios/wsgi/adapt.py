from collections.abc import Iterable
from urllib.parse import quote
from wsgiref.types import StartResponse, WSGIEnvironment

from werkzeug.datastructures import EnvironHeaders
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser
from werkzeug.http import parse_options_header
from werkzeug.wsgi import get_host

from helios.http import (
	File,
	Files,
	Headers,
	Input,
	Method,
	Query,
	Request,
	Response,
	Stream,
	URL,
)
from helios.http.error import BadRequestError, ContentTooLargeError


class ResponseAdapter:
	def __init__(self, response: Response, start_response: StartResponse):
		self.response = response
		self.start_response = start_response

	def adapt(self) -> Iterable[bytes]:
		headers = list(self.response.headers)
		headers += list(self.response.cookies.to_headers())
		self.start_response(str(self.response.status), headers)
		if isinstance(self.response.body, Stream):
			return self.response.body.chunks
		else:
			return [self.response.body.to_bytes()]


class RequestAdapter:
	def __init__(self, environment: WSGIEnvironment):
		self.environment = environment

	def adapt(self) -> Request:
		input, files = self.data()
		return Request(
			self.method(),
			self.url(),
			self.headers(),
			input,
			files,
		)

	def method(self) -> Method:
		return Method.parse(self.environment["REQUEST_METHOD"])

	def url(self) -> URL:
		host = get_host(self.environment)
		if not host:
			raise BadRequestError("invalid Host header")

		origin = URL.parse(f"{self.environment["wsgi.url_scheme"]}://{host}")
		return URL(
			self.path(),
			Query.parse(self.query()),
			scheme=origin.scheme,
			host=origin.host,
			port=origin.port,
		)

	def path(self) -> str:
		script = self.environment.get("SCRIPT_NAME", "")
		info = self.environment.get("PATH_INFO", "")
		raw = (script + info).encode("latin-1")
		return quote(raw, safe=PATH_SAFE) or "/"

	def query(self) -> str:
		raw = self.environment.get("QUERY_STRING", "").encode("latin-1")
		return quote(raw, safe=QUERY_SAFE)

	def headers(self) -> Headers:
		return Headers(dict(EnvironHeaders(self.environment)))

	def data(self) -> tuple[Input, Files]:
		if "CONTENT_TYPE" not in self.environment:
			return Input(), Files()

		mime_type, _ = parse_options_header(self.environment["CONTENT_TYPE"])
		if mime_type not in {
			"application/x-www-form-urlencoded",
			"multipart/form-data",
		}:
			return Input(), Files()

		parser = FormDataParser(
			max_form_memory_size=500_000,
			max_form_parts=1_000,
		)
		try:
			_, form, uploads = parser.parse_from_environ(self.environment)
		except RequestEntityTooLarge as error:
			raise ContentTooLargeError("form data exceeds limits") from error
		input_items = dict(form.lists())

		file_items: dict[str, list[File]] = {}
		for name, storages in uploads.lists():
			file_items[name] = [
				File(
					storage.read(),
					storage.filename or "",
					storage.content_type or "application/octet-stream",
				)
				for storage in storages
			]

		return Input(input_items), Files(file_items)


# WSGI servers hand over the path decoded and the query string as sent, both as
# latin-1 strings of the original bytes. These re-encode only what a URL can't
# carry literally, so an escaped query keeps its escapes.
PATH_SAFE = "!$&'()*+,/:;=@"
QUERY_SAFE = "!$&'()*+,/:;=?@%"
