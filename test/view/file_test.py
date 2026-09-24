import os
from pathlib import Path
from tempfile import TemporaryDirectory

from jinja2 import TemplateNotFound, TemplateSyntaxError
from luna.test.assertion import assert_eq, assert_raises

from helios.view import Engine, Helpers, file


def test_directory_renders_application_helpers():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("{{ site }}")

		engine = Engine(file.Driver(views_dir), Helpers(globals={"site": "Cork"}))

		assert_eq(engine.render("index"), "Cork")


def test_renders_nested_directory_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "index.html").write_text("<h1>Boards</h1>")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("boards.index"), "<h1>Boards</h1>")


def test_directory_rejects_syntax_errors_on_creation():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("boards").mkdir()
		views_dir.joinpath("boards", "show.html").write_text("<h1>Show</h1>")
		broken_file = views_dir.joinpath("boards", "index.html")
		broken_file.write_text("<h1>{{ title }}</h1>\n{% if title %}\n")

		with assert_raises(TemplateSyntaxError) as raised:
			Engine(file.Driver(views_dir))

		exception = raised.exception
		assert exception is not None
		assert_eq(exception.filename, str(broken_file))
		assert_eq(exception.lineno, 2)


def test_directory_rejects_names_outside_directory():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir, "engine")
		views_dir.mkdir()
		Path(dir, "secret.html").write_text("secret")
		engine = Engine(file.Driver(views_dir))

		with assert_raises(TemplateNotFound):
			engine.render("..secret")


def test_directory_reloads_changed_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		engine = Engine(file.Driver(views_dir), reload=True)

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(engine.render("index"), "After")


def test_directory_rejects_deleted_templates_when_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Index")
		engine = Engine(file.Driver(views_dir), reload=True)

		template_file.unlink()

		with assert_raises(TemplateNotFound):
			engine.render("index")


def test_directory_keeps_compiled_templates_when_not_reloading():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		engine = Engine(file.Driver(views_dir))

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(engine.render("index"), "Before")


def test_directory_ignores_hidden_files():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		views_dir.joinpath(".#index.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("index"), "<h1>Index</h1>")


def test_directory_ignores_hidden_directories():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		hidden_dir = views_dir.joinpath(".drafts")
		hidden_dir.mkdir()
		hidden_dir.joinpath("show.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render("index"), "<h1>Index</h1>")
