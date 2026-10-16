from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import (
	assert_eq,
	assert_not,
	assert_raises,
	assert_that,
)

from helios.assets import Bundler, BundlerNotFoundError, Compiled, Manifest


def test_compiles_nothing_without_entries():
	with TemporaryDirectory() as directory:
		root = Path(directory)
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=Path(root, "public", "assets"),
			scripts=[],
			styles=[],
			minify=False,
			sourcemap=False,
		)

	assert_eq(compiled, Compiled(manifest=Manifest(scripts={}, styles={}), files=[]))


def test_empties_output_without_entries():
	with TemporaryDirectory() as directory:
		root = Path(directory)
		output = Path(root, "public", "assets")
		stale = Path(output, "scripts", f"main-{uuid4().hex}.js")
		stale.parent.mkdir(parents=True)
		stale.write_text("")
		bundler = Bundler(root)

		bundler.compile(
			Path(root, "assets"),
			output=output,
			scripts=[],
			styles=[],
			minify=False,
			sourcemap=False,
		)

		assert_that(output.is_dir())
		assert_not(stale.parent.exists())


def test_raises_for_entries_without_esbuild():
	with TemporaryDirectory() as directory:
		root = Path(directory)
		bundler = Bundler(root)

		with assert_raises(BundlerNotFoundError):
			bundler.compile(
				Path(root, "assets"),
				output=Path(root, "public", "assets"),
				scripts=["main"],
				styles=[],
				minify=False,
				sourcemap=False,
			)
