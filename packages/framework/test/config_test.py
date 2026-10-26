from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises

from helios.config import ConfigError, Environment
from helios.url import URL


def test_loads_path():
	environment = Environment.load({"EXAMPLE_FILES_DIR": "/srv/example"})

	assert_eq(environment.path("EXAMPLE_FILES_DIR", Path("data")), Path("/srv/example"))


def test_defaults_path():
	environment = Environment.load({})

	assert_eq(environment.path("EXAMPLE_FILES_DIR", Path("data")), Path("data"))


def test_process_environment_takes_precedence_over_dotenv():
	with TemporaryDirectory() as dir:
		env_file = Path(dir, ".env")
		env_file.write_text("EXAMPLE_FILES_DIR=/dotenv\n")
		environment = Environment.load(
			{"EXAMPLE_FILES_DIR": "/environment"},
			env_file,
		)

	assert_eq(environment.path("EXAMPLE_FILES_DIR", Path("data")), Path("/environment"))


def test_loads_text():
	environment = Environment.load({"EXAMPLE_BUCKET": "example-backups"})

	assert_eq(environment.text("EXAMPLE_BUCKET"), "example-backups")


def test_defaults_text():
	environment = Environment.load({})

	assert_eq(environment.text("EXAMPLE_BUCKET", "backups"), "backups")


def test_defaults_text_for_empty_value():
	environment = Environment.load({"EXAMPLE_BUCKET": "  "})

	assert_eq(environment.text("EXAMPLE_BUCKET", "backups"), "backups")


def test_defaults_path_for_empty_value():
	environment = Environment.load({"EXAMPLE_FILES_DIR": ""})

	assert_eq(environment.path("EXAMPLE_FILES_DIR", Path("data")), Path("data"))


def test_loads_url():
	environment = Environment.load({"BASE_URL": "https://example.com:8443"})

	assert_eq(str(environment.url("BASE_URL")), "https://example.com:8443")


def test_defaults_url():
	environment = Environment.load({})
	default = URL.parse("http://localhost:8000")

	assert_eq(environment.url("BASE_URL", default), default)


def test_loads_true_boolean():
	environment = Environment.load({"EXAMPLE_RELOAD": "true"})

	assert_eq(environment.boolean("EXAMPLE_RELOAD"), True)


def test_loads_false_boolean():
	environment = Environment.load({"EXAMPLE_RELOAD": "false"})

	assert_eq(environment.boolean("EXAMPLE_RELOAD"), False)


def test_loads_boolean_aliases():
	environment = Environment.load(
		{
			"EXAMPLE_YES": "Yes",
			"EXAMPLE_ON": "ON",
			"EXAMPLE_ONE": "1",
			"EXAMPLE_NO": "no",
			"EXAMPLE_OFF": "off",
			"EXAMPLE_ZERO": "0",
		}
	)

	assert_eq(
		[
			environment.boolean("EXAMPLE_YES"),
			environment.boolean("EXAMPLE_ON"),
			environment.boolean("EXAMPLE_ONE"),
			environment.boolean("EXAMPLE_NO"),
			environment.boolean("EXAMPLE_OFF"),
			environment.boolean("EXAMPLE_ZERO"),
		],
		[True, True, True, False, False, False],
	)


def test_defaults_boolean():
	environment = Environment.load({"EXAMPLE_RELOAD": " "})

	assert_eq(environment.boolean("EXAMPLE_RELOAD", False), False)


def test_raises_for_invalid_boolean():
	environment = Environment.load({"EXAMPLE_RELOAD": "ture"})

	with assert_raises(ConfigError):
		environment.boolean("EXAMPLE_RELOAD", False)


def test_raises_for_missing_boolean():
	environment = Environment.load({})

	with assert_raises(ConfigError):
		environment.boolean("EXAMPLE_RELOAD")


def test_requires_value():
	environment = Environment.load({"EXAMPLE_BUCKET": " example-backups "})

	assert_eq(environment.require("EXAMPLE_BUCKET"), "example-backups")


def test_raises_for_missing_value():
	environment = Environment.load({})

	with assert_raises(ConfigError):
		environment.require("EXAMPLE_BUCKET")


def test_raises_for_empty_value():
	environment = Environment.load({"EXAMPLE_BUCKET": "  "})

	with assert_raises(ConfigError):
		environment.require("EXAMPLE_BUCKET")


def test_raises_for_missing_text():
	environment = Environment.load({})

	with assert_raises(ConfigError):
		environment.text("EXAMPLE_BUCKET")


def test_raises_for_empty_text():
	environment = Environment.load({"EXAMPLE_BUCKET": ""})

	with assert_raises(ConfigError):
		environment.text("EXAMPLE_BUCKET")


def test_raises_for_missing_path():
	environment = Environment.load({})

	with assert_raises(ConfigError):
		environment.path("EXAMPLE_FILES_DIR")


def test_raises_for_empty_path():
	environment = Environment.load({"EXAMPLE_FILES_DIR": ""})

	with assert_raises(ConfigError):
		environment.path("EXAMPLE_FILES_DIR")


def test_raises_for_missing_url():
	environment = Environment.load({})

	with assert_raises(ConfigError):
		environment.url("BASE_URL")


def test_raises_for_empty_url():
	environment = Environment.load({"BASE_URL": ""})

	with assert_raises(ConfigError):
		environment.url("BASE_URL")
