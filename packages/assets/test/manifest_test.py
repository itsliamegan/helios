from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from luna.test.assertion import assert_eq

from helios.assets import Manifest


def test_loads_saved_manifest():
	script = f"main-{uuid4().hex}"
	style = f"main-{uuid4().hex}"
	manifest = Manifest(
		scripts={"main": f"scripts/{script}.js"},
		styles={"main": f"styles/{style}.css"},
	)

	with TemporaryDirectory() as directory:
		path = Path(directory, "manifest.json")
		manifest.save(path)
		loaded = Manifest.load(path)

	assert_eq(loaded, manifest)


def test_loads_manifest_from_json():
	script = f"scripts/main-{uuid4().hex}.js"
	style = f"styles/main-{uuid4().hex}.css"

	with TemporaryDirectory() as directory:
		path = Path(directory, "manifest.json")
		path.write_text(
			f'{{"scripts": {{"main": "{script}"}}, "styles": {{"main": "{style}"}}}}'
		)
		manifest = Manifest.load(path)

	assert_eq(manifest.scripts, {"main": script})
	assert_eq(manifest.styles, {"main": style})
