from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Self


@dataclass(init=False)
class Headers:
	"""A message's headers by case-insensitive name.

	Each header keeps the spelling it was first set with. Iterating yields one
	name and value pair per header, with its values joined by commas, except
	for `Set-Cookie`. A cookie's attributes can contain commas, so each
	`Set-Cookie` value is yielded as its own pair.
	"""

	headers: dict[str, Header]

	def __init__(self, pairs: Mapping[str, str | Sequence[str]] | None = None):
		pairs = pairs or {}
		headers = {}
		for raw_name in pairs:
			name = normalize(raw_name)
			headers[name] = Header(raw_name, pairs[raw_name])
		self.headers = headers

	def __getitem__(self, name: str) -> Header:
		return self.headers[normalize(name)]

	def __setitem__(self, raw_name: str, value: str | Sequence[str] | Header):
		name = normalize(raw_name)
		if isinstance(value, Header):
			# `headers[name] += value` assigns the same header back after adding
			# to it.
			if self.headers.get(name) is value:
				return
			raise TypeError("cannot assign a Header from another field")
		if name in self.headers:
			self.headers[name].set(value)
		else:
			self.headers[name] = Header(raw_name, value)

	def __contains__(self, name: object) -> bool:
		return isinstance(name, str) and normalize(name) in self.headers

	def __iter__(self) -> Iterator[tuple[str, str]]:
		for name in self.headers:
			header = self.headers[name]
			if name == "set-cookie":
				for value in header.values:
					yield header.name, value
			else:
				yield header.name, str(header)


@dataclass(init=False)
class Header:
	"""A header field with its original name and value."""

	name: str
	values: list[str]

	def __init__(self, name: str, values: str | Sequence[str]):
		self.name = name
		self.set(values)

	def set(self, value: str | Sequence[str]):
		values = [value] if isinstance(value, str) else list(value)
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


def normalize(raw_name: str) -> str:
	return raw_name.lower()


def validate(value: str):
	"""Refuse a value with a line break, which could inject another header."""

	if "\r" in value or "\n" in value:
		raise ValueError("header values must not contain newline characters")
