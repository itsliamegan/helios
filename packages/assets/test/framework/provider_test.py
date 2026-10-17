from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import assert_eq, assert_is, assert_raises

from helios.app import Application, Config
from helios.assets import Assets, Manifest, ManifestNotFoundError
import helios.assets.config
import helios.assets.provider
from helios.routing import Router


def config(directory: Path) -> helios.assets.config.Config:
	return helios.assets.config.Config(
		Path(directory, "assets"),
		Path(directory, "public", "assets"),
		scripts=["main"],
		styles=[],
	)


def test_provider_registers_config_before_boot():
	with TemporaryDirectory() as directory:
		assets = config(Path(directory))

		app = Application(
			Config(),
			Router([]),
			[helios.assets.provider.Provider(assets)],
		)

		assert_is(app.container.get(helios.assets.config.Config), assets)


def test_provider_binds_assets_from_the_manifest():
	with TemporaryDirectory() as directory:
		assets = config(Path(directory))
		manifest = Manifest(
			scripts={"main": f"scripts/main-{uuid4().hex}.js"},
			styles={},
		)
		assets.manifest.parent.mkdir(parents=True)
		manifest.save(assets.manifest)
		app = Application(
			Config(),
			Router([]),
			[helios.assets.provider.Provider(assets)],
		)

		app.boot()

	assert_eq(app.container.get(Assets), Assets(manifest, "/assets/"))


def test_provider_fails_to_boot_without_a_manifest():
	with TemporaryDirectory() as directory:
		assets = config(Path(directory))
		app = Application(
			Config(),
			Router([]),
			[helios.assets.provider.Provider(assets)],
		)

		with assert_raises(ManifestNotFoundError):
			app.boot()
