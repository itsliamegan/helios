import os
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

from helios.view import Engine, Helpers, TemplateError, View, file


def test_directory_renders_application_helpers():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("{{ site }}")

		engine = Engine(file.Driver(views_dir), Helpers(globals={"site": "Cork"}))

		assert_eq(engine.render(View("index")), "Cork")


def test_renders_nested_directory_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		views_dir.joinpath("posts", "index.html").write_text("<h1>Posts</h1>")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render(View("posts/index")), "<h1>Posts</h1>")


def test_directory_lists_nested_templates_by_slashed_name():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		views_dir.joinpath("posts", "index.html").write_text("<h1>Posts</h1>")

		assert_eq(file.Driver(views_dir).names(), ["posts/index"])


def test_directory_rejects_dotted_names_for_nested_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		views_dir.joinpath("posts", "index.html").write_text("<h1>Posts</h1>")
		engine = Engine(file.Driver(views_dir))

		with assert_raises(TemplateError):
			engine.render(View("posts.index"))


def test_directory_rejects_syntax_errors_on_creation():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		views_dir.joinpath("posts", "show.html").write_text("<h1>Show</h1>")
		broken_file = views_dir.joinpath("posts", "index.html")
		broken_file.write_text("<h1>{{ title }}</h1>\n{% if title %}\n")

		with assert_raises(TemplateError) as raised:
			Engine(file.Driver(views_dir))

		exception = raised.exception
		assert_eq(exception.path, str(broken_file))
		assert_eq(exception.line, 2)


def test_directory_rejects_names_outside_directory():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir, "engine")
		views_dir.mkdir()
		Path(dir, "secret.html").write_text("secret")
		engine = Engine(file.Driver(views_dir))

		with assert_raises(TemplateError):
			engine.render(View("../secret"))


def test_directory_keeps_compiled_templates():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		template_file = views_dir.joinpath("index.html")
		template_file.write_text("Before")
		os.utime(template_file, (1_000_000, 1_000_000))
		engine = Engine(file.Driver(views_dir))

		template_file.write_text("After")
		os.utime(template_file, (2_000_000, 2_000_000))

		assert_eq(engine.render(View("index")), "Before")


def test_directory_ignores_hidden_files():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		views_dir.joinpath(".#index.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render(View("index")), "<h1>Index</h1>")


def test_directory_ignores_hidden_directories():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("index.html").write_text("<h1>Index</h1>")
		hidden_dir = views_dir.joinpath(".drafts")
		hidden_dir.mkdir()
		hidden_dir.joinpath("show.html").write_bytes(b"\xff")

		engine = Engine(file.Driver(views_dir))

		assert_eq(engine.render(View("index")), "<h1>Index</h1>")


def test_directory_locates_runtime_errors_in_the_template_file():
	with TemporaryDirectory() as dir:
		views_dir = Path(dir)
		views_dir.joinpath("posts").mkdir()
		post_file = views_dir.joinpath("posts", "show.html")
		post_file.write_text("<h1>Post</h1>\n{{ post.title }}")
		engine = Engine(file.Driver(views_dir))

		with assert_raises(TemplateError) as raised:
			engine.render(View("posts/show"))

		assert_eq(raised.exception.path, str(post_file))
		assert_eq(raised.exception.line, 2)
