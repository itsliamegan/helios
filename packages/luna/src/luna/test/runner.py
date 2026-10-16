from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
import sys
import traceback
from types import ModuleType

from luna.cli import Command, argument, option
from luna.test import (
	Case,
	Error,
	Fail,
	Filter,
	Location,
	Output,
	Pass,
	Result,
	Suite,
	Test,
)
from luna.test.reporting import Capture, report


class LunaTest(Command):
	"""Run the test suite."""

	name = "test"
	pattern: str | None = argument(
		default=None,
		help="only run tests matching this name, if provided",
	)
	capture: Capture = option(default=Capture.ALWAYS, help="when to capture output")
	jobs: int | None = option(
		default=None,
		short="j",
		help="maximum number of tests to run in parallel",
	)

	def run(self):
		if self.pattern is None:
			filter = EmptyFilter()
		else:
			filter = TestNameFilter(self.pattern)

		root = Path.cwd()
		# Put the project root on the import path so that test files can import
		# shared modules.
		sys.path.insert(0, str(root))
		suite = discover(root.joinpath("test"))
		results = Runner(self.jobs).run(suite, filter)

		if not results:
			if self.pattern is None:
				message = "no tests found in test/"
			else:
				message = f"no tests match {self.pattern!r}"
			print(f"luna test: error: {message}", file=sys.stderr)
			raise SystemExit(1)

		passed = report(results, self.capture)
		if not passed:
			raise SystemExit(1)


@dataclass
class Runner:
	jobs: int | None = None

	def run(self, suite: Suite, filter: Filter) -> list[Result]:
		selections = []
		for test in suite.tests:
			cases = [
				SelectedCase(index, case)
				for index, case in enumerate(test.cases)
				if filter.match(test, case)
			]
			if cases:
				selections.append(SelectedTest(test, cases))

		if not selections:
			return []

		with ProcessPoolExecutor(max_workers=self.jobs) as executor:
			results = executor.map(run_test, selections)
			return [result for test_results in results for result in test_results]


def discover(test_dir: Path) -> Suite:
	tests = []
	for dir, dirs, files in test_dir.walk():
		dirs.sort()
		for file in sorted(files):
			path = dir.joinpath(file)
			if path.suffix != ".py" or not path.stem.endswith("_test"):
				continue

			relative_path = path.relative_to(test_dir).with_suffix("")
			module = import_from_file(path, ".".join(relative_path.parts))
			cases = [
				Case(name)
				for name, item in module.__dict__.items()
				if name.startswith("test") and callable(item)
			]
			tests.append(Test(relative_path.as_posix(), path.resolve(), cases))
	return Suite(tests)


class EmptyFilter(Filter):
	def match(self, test: Test, case: Case) -> bool:
		return True


class TestNameFilter(Filter):
	def __init__(self, name: str):
		self.name = name

	def match(self, test: Test, case: Case) -> bool:
		return self.name in test.name


@dataclass
class SelectedTest:
	test: Test
	cases: list[SelectedCase]


@dataclass
class SelectedCase:
	index: int
	case: Case


def run_test(selection: SelectedTest) -> list[Result]:
	test = selection.test
	module = import_from_file(test.path, test.name.replace("/", "."))
	return [run_case(test, module, case) for case in selection.cases]


def run_case(test: Test, module: ModuleType, selection: SelectedCase) -> Result:
	case = selection.case
	stdout = StringIO()
	stderr = StringIO()
	with redirect_stdout(stdout), redirect_stderr(stderr):
		try:
			impl = getattr(module, case.name)
			impl()
			error = None
		except AssertionError as caught:
			error = caught
		except Exception as caught:  # noqa: BLE001
			error = caught

	output = Output(stdout.getvalue(), stderr.getvalue())
	if error is None:
		return Pass(test.name, case.name, selection.index, output)
	if isinstance(error, AssertionError):
		return Fail(
			test.name,
			case.name,
			selection.index,
			str(error),
			output,
			location=Location.from_traceback(error.__traceback__, test.path),
		)

	traceback_start = error.__traceback__
	if traceback_start is not None:
		traceback_start = traceback_start.tb_next
	formatted = traceback.format_exception(type(error), error, traceback_start)
	return Error(test.name, case.name, selection.index, "".join(formatted), output)


def import_from_file(path: Path, module_name: str) -> ModuleType:
	spec = spec_from_file_location(module_name, path)
	if spec is None or spec.loader is None:
		raise ImportError(f"Cannot load test module from {path}")

	module = module_from_spec(spec)
	spec.loader.exec_module(module)
	return module
