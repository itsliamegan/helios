from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import (
	assert_eq,
	assert_in,
	assert_not,
	assert_raises,
	assert_that,
)

from helios.assets import (
	Bundler,
	BundlerNotFoundError,
	CompileError,
	Compiled,
	Manifest,
)


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


def test_compiles_script_entry():
	with TemporaryDirectory() as directory:
		root = project(directory)
		output = Path(root, "public", "assets")
		message = uuid4().hex
		write(Path(root, "assets", "scripts", "main.js"), f'console.log("{message}");')
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=output,
			scripts=["main"],
			styles=[],
			minify=False,
			sourcemap=False,
		)

		script = compiled.manifest.scripts["main"]
		assert_that(script.startswith("scripts/main-"))
		assert_eq(compiled.files, [Path(script)])
		assert_in(message, Path(output, script).read_text())


def test_compiles_style_entry():
	with TemporaryDirectory() as directory:
		root = project(directory)
		output = Path(root, "public", "assets")
		write(Path(root, "assets", "styles", "main.css"), "body { color: red; }")
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=output,
			scripts=[],
			styles=["main"],
			minify=False,
			sourcemap=False,
		)

		style = compiled.manifest.styles["main"]
		assert_that(style.startswith("styles/main-"))
		assert_eq(compiled.files, [Path(style)])
		assert_in("color: red", Path(output, style).read_text())


def test_bundles_imported_script():
	with TemporaryDirectory() as directory:
		root = project(directory)
		output = Path(root, "public", "assets")
		message = uuid4().hex
		write(
			Path(root, "assets", "scripts", "main.js"),
			'import { message } from "./message.js";\nconsole.log(message);',
		)
		write(
			Path(root, "assets", "scripts", "message.js"),
			f'export const message = "{message}";',
		)
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=output,
			scripts=["main"],
			styles=[],
			minify=False,
			sourcemap=False,
		)

		script = compiled.manifest.scripts["main"]
		assert_in(message, Path(output, script).read_text())


def test_writes_source_maps():
	with TemporaryDirectory() as directory:
		root = project(directory)
		write(Path(root, "assets", "scripts", "main.js"), "console.log(1);")
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=Path(root, "public", "assets"),
			scripts=["main"],
			styles=[],
			minify=False,
			sourcemap=True,
		)

	script = compiled.manifest.scripts["main"]
	assert_eq(compiled.files, [Path(script), Path(f"{script}.map")])


def test_minifies_entries():
	with TemporaryDirectory() as directory:
		root = project(directory)
		output = Path(root, "public", "assets")
		write(Path(root, "assets", "styles", "main.css"), "body {\n\tcolor: red;\n}")
		bundler = Bundler(root)

		compiled = bundler.compile(
			Path(root, "assets"),
			output=output,
			scripts=[],
			styles=["main"],
			minify=True,
			sourcemap=False,
		)

		style = compiled.manifest.styles["main"]
		assert_eq(Path(output, style).read_text(), "body{color:red}\n")


def test_raises_for_script_importing_stylesheet():
	with TemporaryDirectory() as directory:
		root = project(directory)
		write(Path(root, "assets", "scripts", "main.js"), 'import "./theme.css";')
		write(Path(root, "assets", "scripts", "theme.css"), "body { color: red; }")
		bundler = Bundler(root)

		with assert_raises(CompileError):
			bundler.compile(
				Path(root, "assets"),
				output=Path(root, "public", "assets"),
				scripts=["main"],
				styles=[],
				minify=False,
				sourcemap=False,
			)


def test_raises_for_entry_that_fails_to_compile():
	with TemporaryDirectory() as directory:
		root = project(directory)
		write(Path(root, "assets", "scripts", "main.js"), 'import "./missing.js";')
		bundler = Bundler(root)

		with assert_raises(CompileError):
			bundler.compile(
				Path(root, "assets"),
				output=Path(root, "public", "assets"),
				scripts=["main"],
				styles=[],
				minify=False,
				sourcemap=False,
			)


def project(directory: str) -> Path:
	root = Path(directory)
	Path(root, "node_modules").symlink_to(Path(MEMBER, "node_modules"))
	return root


def write(path: Path, text: str):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(text)


MEMBER = Path(__file__).parents[1]
