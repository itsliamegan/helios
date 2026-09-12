from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

from helios.config import Config, ConfigError
from helios.http import URL


class FilesConfig:
	def __init__(self, dir: Path):
		self.dir = dir


class CustomConfig(Config):
	def __init__(self, values: Mapping[str, str]):
		super().__init__(values)
		self.files = FilesConfig(self.path("EXAMPLE_FILES_DIR", Path("data")))


def test_loads_path():
	loaded = CustomConfig.load({"EXAMPLE_FILES_DIR": "/srv/example"})

	assert_eq(loaded.files.dir, Path("/srv/example"))


def test_defaults_path():
	loaded = CustomConfig.load({})

	assert_eq(loaded.files.dir, Path("data"))


def test_process_environment_takes_precedence_over_dotenv():
	with TemporaryDirectory() as dir:
		env_file = Path(dir, ".env")
		env_file.write_text("EXAMPLE_FILES_DIR=/dotenv\n")
		loaded = CustomConfig.load(
			{"EXAMPLE_FILES_DIR": "/environment"},
			env_file,
		)

	assert_eq(loaded.files.dir, Path("/environment"))


def test_loads_text():
	loaded = Config.load({"EXAMPLE_BUCKET": "example-backups"})

	assert_eq(loaded.text("EXAMPLE_BUCKET"), "example-backups")


def test_defaults_text():
	loaded = Config.load({})

	assert_eq(loaded.text("EXAMPLE_BUCKET", "backups"), "backups")


def test_defaults_text_for_empty_value():
	loaded = Config.load({"EXAMPLE_BUCKET": "  "})

	assert_eq(loaded.text("EXAMPLE_BUCKET", "backups"), "backups")


def test_defaults_path_for_empty_value():
	loaded = CustomConfig.load({"EXAMPLE_FILES_DIR": ""})

	assert_eq(loaded.files.dir, Path("data"))


def test_loads_url():
	loaded = Config.load({"BASE_URL": "https://example.com:8443"})

	assert_eq(str(loaded.url("BASE_URL")), "https://example.com:8443")


def test_defaults_url():
	loaded = Config.load({})
	default = URL("http://localhost:8000")

	assert_eq(loaded.url("BASE_URL", default), default)


def test_requires_value():
	loaded = Config.load({"EXAMPLE_BUCKET": " example-backups "})

	assert_eq(loaded.require("EXAMPLE_BUCKET"), "example-backups")


def test_raises_for_missing_value():
	loaded = Config.load({})

	with assert_raises(ConfigError):
		loaded.require("EXAMPLE_BUCKET")


def test_raises_for_empty_value():
	loaded = Config.load({"EXAMPLE_BUCKET": "  "})

	with assert_raises(ConfigError):
		loaded.require("EXAMPLE_BUCKET")


def test_raises_for_missing_text():
	loaded = Config.load({})

	with assert_raises(ConfigError):
		loaded.text("EXAMPLE_BUCKET")


def test_raises_for_empty_text():
	loaded = Config.load({"EXAMPLE_BUCKET": ""})

	with assert_raises(ConfigError):
		loaded.text("EXAMPLE_BUCKET")


def test_raises_for_missing_path():
	loaded = Config.load({})

	with assert_raises(ConfigError):
		loaded.path("EXAMPLE_FILES_DIR")


def test_raises_for_empty_path():
	loaded = Config.load({"EXAMPLE_FILES_DIR": ""})

	with assert_raises(ConfigError):
		loaded.path("EXAMPLE_FILES_DIR")


def test_raises_for_missing_url():
	loaded = Config.load({})

	with assert_raises(ConfigError):
		loaded.url("BASE_URL")


def test_raises_for_empty_url():
	loaded = Config.load({"BASE_URL": ""})

	with assert_raises(ConfigError):
		loaded.url("BASE_URL")
