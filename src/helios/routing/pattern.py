import re
from typing import Any
from urllib.parse import quote

from helios.http import URL

from . import convert

PARAM_REGEX = re.compile(r"{(\w+)(?::(\w+))?}")
PARAM_VALUE_REGEX = r"[\w-]+"


class Pattern:
	def __init__(self, raw: str):
		self.converters: dict[str, convert.Converter] = {}
		lit = raw
		for param in PARAM_REGEX.finditer(raw):
			name, converter_name = param.groups()
			converter_name = converter_name or "str"
			if converter_name not in convert.CONVERTERS:
				raise ValueError(f"Unknown pattern converter: {converter_name}")
			self.converters[name] = convert.CONVERTERS[converter_name]
			lit = lit.replace(param.group(), f"(?P<{name}>{PARAM_VALUE_REGEX})")

		if lit.endswith("/"):
			lit += "?$"
		else:
			lit += "/?$"
		self.raw = raw
		self.regex = re.compile(lit)

	def prefixed(self, prefix: str) -> Pattern:
		if not prefix:
			return self
		return Pattern(join(prefix, self.raw))

	def match(self, url: URL) -> dict[str, Any] | None:
		match = self.regex.match(url.path)
		if match is None:
			return None
		return self.convert(match.groupdict())

	def path(self, params: dict[str, Any] | None = None) -> str:
		params = params or {}
		expected = set(self.converters)
		supplied = set(params)
		missing = expected - supplied
		unexpected = supplied - expected
		if missing:
			raise ValueError(f"missing route parameters: {", ".join(sorted(missing))}")
		if unexpected:
			raise ValueError(
				f"unexpected route parameters: {", ".join(sorted(unexpected))}"
			)

		def replace(match: re.Match[str]) -> str:
			name = match.group(1)
			value = str(self.converters[name](str(params[name])))
			encoded = quote(value, safe="")
			if re.fullmatch(PARAM_VALUE_REGEX, encoded) is None:
				raise ValueError(f"invalid route parameter: {name}")
			return encoded

		return PARAM_REGEX.sub(replace, self.raw)

	def convert(self, raw_params: dict[str, str]) -> dict[str, Any] | None:
		try:
			return {
				name: self.converters[name](value) for name, value in raw_params.items()
			}
		except ValueError:
			return None

	def __repr__(self) -> str:
		return f"Pattern({self.raw!r})"


def join(prefix: str, raw: str) -> str:
	if not prefix:
		return raw
	if not raw:
		return prefix
	return f"{prefix.rstrip("/")}/{raw.lstrip("/")}"
