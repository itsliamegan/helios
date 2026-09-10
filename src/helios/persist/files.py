from __future__ import annotations

from contextlib import suppress
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Protocol, Self, TextIO, cast

from .config import Config

type JSONValue = (
	None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)


class Format[T](Protocol):
	def encode(self, value: T, /) -> JSONValue: ...
	def decode(self, value: JSONValue, /) -> T: ...


class Handle[T](Protocol):
	def load(self) -> T: ...
	def save(self, value: T) -> None: ...


class Persistence(Protocol):
	def open[T](self, file: JSONFile[T]) -> Handle[T]: ...


class PersistenceError(Exception):
	pass


class FormatError(PersistenceError):
	pass


class FilePersistence:
	def __init__(self, files: Files):
		self.files = files
		self.lock: TextIO | None = None
		self.handles: dict[JSONFile[Any], FileHandle[Any]] = {}

	def __enter__(self) -> Self:
		if self.lock is not None:
			raise RuntimeError("file persistence is already active")

		lock = None
		try:
			lock = self.files.lock_file.open("a+")
			fcntl.flock(lock, fcntl.LOCK_EX)
		except BaseException as error:
			if lock is not None:
				with suppress(BaseException):
					lock.close()
			if isinstance(error, OSError):
				raise PersistenceError(
					f"could not acquire persistence lock {self.files.lock_file}"
				) from error
			raise

		self.lock = lock
		return self

	def __exit__(self, *_):
		for handle in self.handles.values():
			handle.close()
		self.handles.clear()

		lock = self.lock
		self.lock = None
		if lock is None:
			return

		try:
			try:
				fcntl.flock(lock, fcntl.LOCK_UN)
			finally:
				lock.close()
		except OSError as error:
			raise PersistenceError(
				f"could not release persistence lock {self.files.lock_file}"
			) from error

	def open[T](self, file: JSONFile[T]) -> Handle[T]:
		if self.lock is None:
			raise RuntimeError("file persistence is not active")
		if self.files is not file.files:
			raise RuntimeError("persistence file belongs to a different file set")

		handle = self.handles.get(file)
		if handle is None:
			handle = FileHandle(file)
			self.handles[file] = handle
		return cast(Handle[T], handle)


class Files:
	def __init__(self, config: Config):
		self.lock_file = config.lock_file

	def json[T](self, path: Path, format: Format[T]) -> JSONFile[T]:
		return JSONFile(self, path, format)

	def lock(self) -> FilePersistence:
		return FilePersistence(self)


class FileHandle[T]:
	def __init__(self, file: JSONFile[T]):
		self.file = file
		self.active = True
		self.loaded = False
		self.value: T | None = None

	def load(self) -> T:
		self.ensure_active()
		if not self.loaded:
			self.value = self.file.load()
			self.loaded = True
		return cast(T, self.value)

	def save(self, value: T) -> None:
		self.ensure_active()
		self.file.save(value)
		self.value = value
		self.loaded = True

	def close(self) -> None:
		self.active = False

	def ensure_active(self) -> None:
		if not self.active:
			raise RuntimeError("persistence handle is not active")


class JSONFile[T]:
	def __init__(self, files: Files, path: Path, format: Format[T]):
		self.files = files
		self.path = path
		self.format = format

	def load(self) -> T:
		try:
			with self.path.open() as file:
				value = cast(JSONValue, json.load(file))
		except Exception as error:
			raise PersistenceError(f"could not load file {self.path}") from error

		try:
			return self.format.decode(value)
		except Exception as error:
			raise FormatError(f"could not decode file {self.path}") from error

	def save(self, value: T) -> None:
		try:
			encoded = self.format.encode(value)
		except Exception as error:
			raise FormatError(f"could not encode file {self.path}") from error

		try:
			serialized = json.dumps(encoded)
		except Exception as error:
			raise PersistenceError(f"could not serialize file {self.path}") from error

		temp_path = None
		try:
			try:
				mode = stat.S_IMODE(self.path.stat().st_mode)
			except FileNotFoundError:
				mode = None

			with tempfile.NamedTemporaryFile(
				mode="w",
				dir=self.path.parent,
				prefix=f".{self.path.name}.",
				suffix=".tmp",
				delete=False,
			) as temp_file:
				temp_path = Path(temp_file.name)
				temp_file.write(serialized)
				if mode is not None:
					os.fchmod(temp_file.fileno(), mode)

			os.replace(temp_path, self.path)
			temp_path = None
		except OSError as error:
			raise PersistenceError(f"could not save file {self.path}") from error
		finally:
			if temp_path is not None:
				with suppress(OSError):
					temp_path.unlink(missing_ok=True)
