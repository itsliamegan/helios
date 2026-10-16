from dataclasses import dataclass
import linecache
from pathlib import Path
import textwrap
import traceback
from types import TracebackType
from typing import Protocol


@dataclass
class Location:
	path: Path
	line: int
	source: str

	@staticmethod
	def from_traceback(
		traceback_start: TracebackType | None,
		path: Path,
	) -> Location | None:
		# Frames run from outermost to innermost, so the first frame in the test
		# file is the line in the test function. Later frames in the same file
		# belong to helpers it called and are skipped.
		for frame in traceback.extract_tb(traceback_start):
			if Path(frame.filename) != path or frame.lineno is None:
				continue

			end = frame.end_lineno or frame.lineno
			lines = linecache.getlines(frame.filename)[frame.lineno - 1 : end]
			source = textwrap.dedent("".join(lines)).rstrip()
			return Location(path, frame.lineno, source)
		return None


class Output:
	def __init__(self, stdout: str, stderr: str):
		self.stdout = stdout
		self.stderr = stderr


class Result:
	def __init__(
		self,
		test_name: str,
		case_name: str,
		case_index: int,
		output: Output,
	):
		self.test_name = test_name
		self.case_name = case_name
		self.case_index = case_index
		self.output = output


class Pass(Result):
	pass


class Fail(Result):
	def __init__(
		self,
		test_name: str,
		case_name: str,
		case_index: int,
		error: str,
		output: Output,
		location: Location | None = None,
	):
		super().__init__(test_name, case_name, case_index, output)
		self.error = error
		self.location = location


class Error(Result):
	def __init__(
		self,
		test_name: str,
		case_name: str,
		case_index: int,
		error: str,
		output: Output,
	):
		super().__init__(test_name, case_name, case_index, output)
		self.error = error


class Case:
	def __init__(self, name: str):
		self.name = name

	def __repr__(self) -> str:
		return f"Case(name={self.name!r})"


class Test:
	def __init__(self, name: str, path: Path, cases: list[Case]):
		self.name = name
		self.path = path
		self.cases = cases

	def __repr__(self) -> str:
		return f"Test(name={self.name!r}, path={self.path!r}, cases={self.cases!r})"


class Suite:
	def __init__(self, tests: list[Test]):
		self.tests = tests

	def __repr__(self) -> str:
		return f"Suite(tests={self.tests!r})"


class Filter(Protocol):
	def match(self, test: Test, case: Case) -> bool: ...
