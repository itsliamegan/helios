from collections.abc import Iterable
from urllib.parse import parse_qs as parse_query
from urllib.parse import urlparse as parse_url
from wsgiref.types import StartResponse, WSGIEnvironment

from werkzeug.datastructures import EnvironHeaders, FileStorage
from werkzeug.formparser import FormDataParser
from werkzeug.http import parse_options_header
from werkzeug.wsgi import get_current_url

from helios.http import (
	File,
	Files,
	Headers,
	Input,
	Method,
	Request,
	Response,
	Stream,
	URL,
)


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
		return Method(self.environment["REQUEST_METHOD"])

	def url(self) -> URL:
		raw = get_current_url(self.environment)
		parsed = parse_url(raw)
		query = parse_query(parsed.query, keep_blank_values=True)
		return URL(parsed.path, {name: unwrap(vals) for name, vals in query.items()})

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
		_, form, uploads = parser.parse_from_environ(self.environment)
		input = Input({name: unwrap(values) for name, values in form.lists()})
		files = Files(
			{
				name: unwrap([adapt_file(storage) for storage in storages])
				for name, storages in uploads.lists()
			}
		)
		return input, files


def adapt_file(storage: FileStorage) -> File:
	return File(
		storage.read(),
		storage.filename or "",
		storage.content_type or "application/octet-stream",
	)


def unwrap[T](values: list[T]) -> T | list[T]:
	return values[0] if len(values) == 1 else values
