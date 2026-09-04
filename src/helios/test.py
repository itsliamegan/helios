from collections.abc import Callable
from io import StringIO
import sys

class Result:
	def __init__(self, test: "Test", case: "Case"):
		self.test = test
		self.case = case

class Pass(Result):
	pass

class Fail(Result):
	def __init__(self, test: "Test", case: "Case", err: AssertionError):
		super().__init__(test, case)
		self.err = err

class Error(Result):
	def __init__(self, test: "Test", case: "Case", err: Exception):
		super().__init__(test, case)
		self.err = err

class Filter:
	def match(self, case: Case) -> bool:
		raise NotImplementedError

class EmptyFilter(Filter):
	def match(self, case: Case) -> bool:
		return True

class TestNameFilter(Filter):
	def __init__(self, name: str):
		self.name = name

	def match(self, case: Case) -> bool:
		return case.test.name == self.name

class Case:
	def __init__(self, test: "Test", name: str, impl: Callable[[], None]):
		self.test = test
		self.name = name
		self.impl = impl

	def run(self):
		stdout = sys.stdout
		stderr = sys.stderr
		sys.stdout = StringIO()
		sys.stderr = StringIO()
		try:
			self.impl()
			return Pass(self.test, self)
		except AssertionError as err:
			return Fail(self.test, self, err)
		except Exception as err:
			return Error(self.test, self, err)
		finally:
			sys.stdout = stdout
			sys.stderr = stderr

	def __repr__(self) -> str:
		return f"Case(name={repr(self.name)}, impl={repr(self.impl)})"

class Test:
	def __init__(self, name: str, cases: list[Case]):
		self.name = name
		self.cases = cases

	def run(self, filter: Filter) -> list[Result]:
		results = []
		for case in self.cases:
			if filter.match(case):
				results.append(case.run())
		return results

	def __repr__(self) -> str:
		return f"Test(name={repr(self.name)}, cases={repr(self.cases)})"

class Suite:
	def __init__(self, tests: list[Test]):
		self.tests = tests

	def run(self, filter: Filter) -> list[Result]:
		results = []
		for test in self.tests:
			results += test.run(filter)
		return results

	def __repr__(self) -> str:
		return f"Suite(tests={repr(self.tests)})"

def report(results: list[Result]):
	for result in results:
		if isinstance(result, Pass):
			desc = "PASS"
		elif isinstance(result, Fail):
			desc = "FAIL"
		elif isinstance(result, Error):
			desc = "ERROR"

		print(f"{desc}\t{result.test.name}:{result.case.name}")

		if isinstance(result, Fail) or isinstance(result, Error):
			import traceback
			stack = traceback.extract_tb(result.err.__traceback__)
			frame = stack[-1]
			print(f"\t{frame.line}")
			if isinstance(result, Error):
				traceback.print_exception(result.err)


def main():
	from importlib.util import spec_from_file_location, module_from_spec
	from pathlib import Path
	import sys
	from types import ModuleType

	def import_from_file(path: Path) -> ModuleType:
		spec = spec_from_file_location(path.stem, path)
		module = module_from_spec(spec)
		spec.loader.exec_module(module)
		return module

	if len(sys.argv) == 2:
		filter = TestNameFilter(sys.argv[1])
	else:
		filter = EmptyFilter()

	test_dir = Path.cwd().joinpath("test")
	tests = []
	for (dir, dirs, files) in test_dir.walk():
		for file in files:
			path = dir.joinpath(file)
			if path.suffix == ".py" and path.stem.endswith("_test"):
				module = import_from_file(path)
				cases = []
				test = Test(path.stem, cases)
				for (name, item) in module.__dict__.items():
					if name.startswith("test") and callable(item):
						case = Case(test, name, item)
						cases.append(case)
				tests.append(test)
	suite = Suite(tests)
	results = suite.run(filter)

	report(results)
