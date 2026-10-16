from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from luna import ansi
from luna.ansi import Escape
from luna.test import Error, Fail, Pass, Result


class Capture(StrEnum):
	ALWAYS = "always"
	PASS = "pass"
	NEVER = "never"


def report(results: Sequence[Result], capture: Capture = Capture.ALWAYS) -> bool:
	def sort_key(result: Result) -> tuple[str, int]:
		return result.test_name, result.case_index

	passed = True
	for result in sorted(results, key=sort_key):
		if isinstance(result, Pass):
			desc = ansi.escape(Escape.GREEN, "PASS")
		elif isinstance(result, Fail):
			desc = ansi.escape(Escape.RED, "FAIL")
			passed = False
		elif isinstance(result, Error):
			desc = ansi.escape(Escape.YELLOW, "ERROR")
			passed = False

		print(f"{desc}\t{result.test_name}:{result.case_name}")

		if isinstance(result, Fail) and result.location is not None:
			location = result.location
			path = location.path.relative_to(Path.cwd(), walk_up=True)
			print(f"\t{path}:{location.line}")
			for line in location.source.splitlines():
				print(f"\t    {line}")

		if isinstance(result, (Fail, Error)) and result.error:
			for line in result.error.splitlines():
				print(f"\t{line}")

		if capture is Capture.NEVER or (
			capture is Capture.PASS and isinstance(result, (Fail, Error))
		):
			print(result.output.stdout, end="")
			print(result.output.stderr, end="")

	return passed
