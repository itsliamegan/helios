from contextlib import chdir, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.test.assertion import assert_eq, assert_raises, assert_that

from helios.app import Application, Config
from helios.assets import Manifest
import helios.assets.config
import helios.assets.provider
from helios.console import Program
from helios.routing import Router


def test_compile_saves_the_manifest_in_the_output_directory():
	assets = helios.assets.config.Config(
		Path("assets"),
		Path("public", "assets"),
		scripts=[],
		styles=[],
	)
	app = Application(Config(), Router([]), [helios.assets.provider.Provider(assets)])

	with TemporaryDirectory() as directory, chdir(directory):
		Program.main(["assets:compile"], app)

		manifest = Manifest.load(Path(directory, "public", "assets", "manifest.json"))

	assert_eq(manifest, Manifest(scripts={}, styles={}))


def test_compile_fails_without_an_assets_configuration():
	app = Application(Config(), Router([]), [])
	stderr = StringIO()

	with redirect_stderr(stderr), assert_raises(SystemExit) as raised:
		Program.main(["assets:compile"], app)

	assert_eq(raised.exception.code, 1)
	assert_that(stderr.getvalue().startswith("helios: error: "))
