from jinja2 import TemplateError as JinjaTemplateError
from jinja2 import TemplateNotFound, TemplateSyntaxError


class ComponentError(TypeError):
	pass


class TemplateError(Exception):
	"""A template failed to compile or render.

	The path and line locate the failure in the template's source. Each is None
	when unknown, as for a template without a file or a missing template.
	"""

	path: str | None
	line: int | None

	def __init__(
		self,
		message: str,
		*,
		path: str | None = None,
		line: int | None = None,
	):
		location = []
		if path is not None:
			location.append(path)
		if line is not None:
			location.append(f"line {line}")
		if location:
			message = f"{message} ({", ".join(location)})"

		super().__init__(message)
		self.path = path
		self.line = line

	@classmethod
	def from_jinja(cls, error: JinjaTemplateError) -> TemplateError:
		if isinstance(error, TemplateSyntaxError):
			return cls(error.message or "", path=error.filename, line=error.lineno)

		if isinstance(error, TemplateNotFound):
			message = f'Template "{error.name}" does not exist'
		else:
			message = str(error)

		# Jinja rewrites the traceback so that template frames carry the
		# template's file name and line. Those frames are the ones whose globals
		# hold the exception, and a template without a file is named <template>.
		path = None
		line = None
		frame = error.__traceback__
		while frame is not None:
			if "__jinja_exception__" in frame.tb_frame.f_globals:
				path = frame.tb_frame.f_code.co_filename
				line = frame.tb_lineno
			frame = frame.tb_next
		if path == "<template>":
			path = None

		return cls(message, path=path, line=line)
