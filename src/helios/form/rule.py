from typing import Protocol


class RuleError(ValueError):
	def __init__(self, message: str | None = None):
		super().__init__(message)
		self.message = message


class Rule[In, Out](Protocol):
	@property
	def name(self) -> str: ...

	@property
	def message(self) -> str: ...

	def check(self, value: In) -> Out: ...


class Required:
	name = "required"
	message = "must be provided"

	def check[T](self, value: T | None) -> T:
		if value is None:
			raise RuleError()
		else:
			return value
