from contextlib import suppress
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, TextIO, cast
from uuid import UUID

from .store import Session, Store


class DriverError(RuntimeError):
	pass


class Driver:
	def __init__(self, path: Path, lock_path: Path):
		self.path = path
		self.lock_path = lock_path

	def open(self) -> FileScope:
		return FileScope(self)

	def load(self) -> Store:
		try:
			with self.path.open() as file:
				value = json.load(file)
		except Exception as error:
			raise DriverError(f"could not load session file {self.path}") from error
		try:
			return decode(value)
		except Exception as error:
			raise DriverError(f"could not decode session file {self.path}") from error

	def save(self, store: Store):
		try:
			serialized = json.dumps(encode(store))
		except Exception as error:
			raise DriverError(f"could not encode session file {self.path}") from error

		temporary_path = None
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
			) as temporary_file:
				temporary_path = Path(temporary_file.name)
				temporary_file.write(serialized)
				if mode is not None:
					os.fchmod(temporary_file.fileno(), mode)
			os.replace(temporary_path, self.path)
			temporary_path = None
		except OSError as error:
			raise DriverError(f"could not save session file {self.path}") from error
		finally:
			if temporary_path is not None:
				with suppress(OSError):
					temporary_path.unlink(missing_ok=True)


class FileScope:
	def __init__(self, driver: Driver):
		self.driver = driver
		self.lock: TextIO | None = None

	def __enter__(self) -> Store:
		lock = None
		try:
			lock = self.driver.lock_path.open("a+")
			fcntl.flock(lock, fcntl.LOCK_EX)
			store = self.driver.load()
		except BaseException as error:
			if lock is not None:
				with suppress(BaseException):
					lock.close()
			if isinstance(error, OSError):
				raise DriverError(
					f"could not acquire session lock {self.driver.lock_path}"
				) from error
			raise
		self.lock = lock
		return store

	def __exit__(self, exception_type, exception, traceback):
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
			raise DriverError(
				f"could not release session lock {self.driver.lock_path}"
			) from error


def encode(store: Store) -> dict[str, Any]:
	data = {}
	for id, session in store.sessions.items():
		data[str(id)] = {
			"items": session.items,
			"last_active_at": (
				session.last_active_at.isoformat()
				if session.last_active_at is not None
				else None
			),
		}
	return data


def decode(value: object) -> Store:
	if not isinstance(value, dict):
		raise TypeError("expected a session object")
	sessions = {}
	for raw_id, raw_session in value.items():
		if not isinstance(raw_id, str) or not isinstance(raw_session, dict):
			raise TypeError("expected a session entry")
		items = raw_session["items"]
		if not isinstance(items, dict):
			raise TypeError("expected session items")
		raw_last_active_at = raw_session["last_active_at"]
		if raw_last_active_at is not None and not isinstance(raw_last_active_at, str):
			raise TypeError("expected session activity time")
		id = UUID(raw_id)
		last_active_at = (
			datetime.fromisoformat(raw_last_active_at)
			if raw_last_active_at is not None
			else None
		)
		sessions[id] = Session(id, cast(dict[str, Any], items), last_active_at)
	return Store(sessions)
