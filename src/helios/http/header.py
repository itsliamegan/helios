from collections.abc import Iterator
from dataclasses import dataclass
from typing import Self


@dataclass(init=False)
class Header:
	name: str
	values: list[str]

	def __init__(self, name: str, values: str | list[str]):
		self.name = name
		self.set(values)

	def set(self, value: str | list[str]):
		values = value if isinstance(value, list) else [value]
		for item in values:
			validate(item)
		self.values = values

	def __iadd__(self, other: str) -> Self:
		validate(other)
		self.values.append(other)
		return self

	def __iter__(self) -> Iterator[str]:
		return iter(self.values)

	def __str__(self) -> str:
		return ", ".join(self.values)


@dataclass(init=False)
class Headers:
	headers: dict[str, Header]

	def __init__(self, pairs: dict[str, str | list[str]] | None = None):
		pairs = pairs or {}
		headers = {}
		for raw_name in pairs:
			name = normalize(raw_name)
			headers[name] = Header(raw_name, pairs[raw_name])
		self.headers = headers

	def __getitem__(self, name: str) -> Header:
		return self.headers[normalize(name)]

	def __setitem__(self, raw_name: str, value: str | list[str] | Header):
		name = normalize(raw_name)
		if isinstance(value, Header):
			if self.headers.get(name) is value:
				return
			raise TypeError("cannot assign a Header from another field")
		if name in self.headers:
			self.headers[name].set(value)
		else:
			self.headers[name] = Header(raw_name, value)

	def __contains__(self, name: str) -> bool:
		return normalize(name) in self.headers

	def __iter__(self) -> Iterator[tuple[str, str]]:
		for name in self.headers:
			header = self.headers[name]
			if name == "set-cookie":
				for value in header.values:
					yield header.name, value
			else:
				yield header.name, str(header)


def normalize(raw_name: str) -> str:
	return raw_name.lower()


def validate(value: str):
	if "\r" in value or "\n" in value:
		raise ValueError("header values must not contain newline characters")
