from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
import re
from typing import Any, ClassVar, Self
from urllib.parse import quote

from helios.http import URL

from .convert import Converter


@dataclass
class Pattern:
	segments: tuple[Text | Parameter, ...]
	trailing_slash: bool = False

	@classmethod
	def parse(cls, text: str) -> Self:
		segments = []
		for part in text.strip("/").split("/"):
			if not part:
				continue
			parameter = Parameter.parse(part)
			if parameter is not None:
				segments.append(parameter)
			elif "{" in part or "}" in part:
				raise ValueError(f"route segment mixes text and a parameter: {part!r}")
			else:
				segments.append(Text(part))
		return cls(tuple(segments), text.endswith("/"))

	@cached_property
	def parameters(self) -> dict[str, Parameter]:
		parameters = {}
		for segment in self.segments:
			if isinstance(segment, Parameter):
				parameters[segment.name] = segment
		return parameters

	@cached_property
	def regex(self) -> re.Pattern[str]:
		expression = "".join(f"/{segment.expression}" for segment in self.segments)
		return re.compile(f"{expression}/?$")

	@property
	def is_empty(self) -> bool:
		return not self.segments and not self.trailing_slash

	def prefixed(self, prefix: Pattern) -> Self:
		if self.is_empty:
			return type(self)(prefix.segments, prefix.trailing_slash)
		else:
			return type(self)((*prefix.segments, *self.segments), self.trailing_slash)

	def match(self, url: URL) -> dict[str, Any] | None:
		match = self.regex.match(url.path)
		if match is None:
			return None
		return self.convert(match.groupdict())

	def path(self, parameters: Mapping[str, Any] | None = None) -> str:
		parameters = parameters or {}
		expected = set(self.parameters)
		supplied = set(parameters)
		missing = expected - supplied
		unexpected = supplied - expected
		if missing:
			raise ValueError(f"missing route parameters: {", ".join(sorted(missing))}")
		if unexpected:
			raise ValueError(
				f"unexpected route parameters: {", ".join(sorted(unexpected))}"
			)

		parts = []
		for segment in self.segments:
			if isinstance(segment, Parameter):
				parts.append(segment.format(parameters[segment.name]))
			else:
				parts.append(segment.text)
		path = "/" + "/".join(parts)
		if parts and self.trailing_slash:
			path += "/"
		return path

	def convert(self, raw_parameters: Mapping[str, str]) -> dict[str, Any] | None:
		try:
			return {
				name: self.parameters[name].converter.convert(value)
				for name, value in raw_parameters.items()
			}
		except ValueError:
			return None


@dataclass
class Text:
	text: str

	@property
	def expression(self) -> str:
		return re.escape(self.text)


@dataclass
class Parameter:
	syntax: ClassVar[re.Pattern[str]] = re.compile(r"{(\w+)(?::(\w+))?}")
	value_syntax: ClassVar[re.Pattern[str]] = re.compile(r"[\w-]+")

	name: str
	converter: Converter[Any]

	@classmethod
	def parse(cls, text: str) -> Self | None:
		match = cls.syntax.fullmatch(text)
		if match is None:
			return None

		name, converter_name = match.groups()
		converter_name = converter_name or "str"
		converter = Converter.for_name(converter_name)
		if converter is None:
			raise ValueError(f"Unknown pattern converter: {converter_name}")
		return cls(name, converter)

	@property
	def expression(self) -> str:
		return f"(?P<{self.name}>{self.value_syntax.pattern})"

	def format(self, value: Any) -> str:
		encoded = quote(self.converter.format(value), safe="")
		if self.value_syntax.fullmatch(encoded) is None:
			raise ValueError(f"invalid route parameter: {self.name}")
		return encoded
