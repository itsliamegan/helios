from jinja2 import TemplateError as JinjaTemplateError
from jinja2 import TemplateNotFound, TemplateSyntaxError


class ComponentError(TypeError):
	"""Raised when a component class is declared incorrectly."""


class TemplateError(Exception):
	"""A template failed to compile or render."""

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

		# Walk the exception traceback to find the original file name and line
		# number.
		path = None
		line = None
		frame = error.__traceback__
		while frame is not None:
			# Jinja marks a frame as synthetic with a global.
			if "__jinja_exception__" in frame.tb_frame.f_globals:
				path = frame.tb_frame.f_code.co_filename
				line = frame.tb_lineno
			frame = frame.tb_next
		# Ignore Jinja's placeholder name if the template has no file name.
		if path == "<template>":
			path = None

		return cls(message, path=path, line=line)
