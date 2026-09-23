from collections.abc import Mapping
import os
from pathlib import Path
from typing import Self

from dotenv import dotenv_values

from helios.http import URL


class ConfigError(Exception):
	pass


TRUE_VALUES = {"true", "yes", "on", "1"}
FALSE_VALUES = {"false", "no", "off", "0"}


class Config:
	def __init__(self, values: dict[str, str]):
		self.values = values

	@classmethod
	def load(
		cls,
		env: Mapping[str, str] | None = None,
		env_file: Path | None = None,
	) -> Self:
		if env is None:
			env = os.environ

		values = {}
		if env_file is not None:
			values.update(
				{
					name: value
					for name, value in dotenv_values(env_file).items()
					if value is not None
				}
			)
		values.update(env)
		return cls(values)

	def value(self, name: str) -> str | None:
		return self.values.get(name, "").strip() or None

	def text(self, name: str, default: str | None = None) -> str:
		if self.value(name) is None and default is not None:
			return default
		return self.require(name)

	def path(self, name: str, default: Path | None = None) -> Path:
		if self.value(name) is None and default is not None:
			return default
		return Path(self.require(name))

	def url(self, name: str, default: URL | None = None) -> URL:
		if self.value(name) is None and default is not None:
			return default
		return URL(self.require(name))

	def boolean(self, name: str, default: bool | None = None) -> bool:
		if self.value(name) is None and default is not None:
			return default
		value = self.require(name).lower()
		if value in TRUE_VALUES:
			return True
		if value in FALSE_VALUES:
			return False
		raise ConfigError(f"configuration value {name} must be true or false")

	def require(self, name: str) -> str:
		value = self.value(name)
		if value is None:
			raise ConfigError(f"missing configuration value {name}")
		return value
