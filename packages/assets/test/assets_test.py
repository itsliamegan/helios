from uuid import uuid4

from luna.test.assertion import (
	assert_eq,
	assert_raises,
)

from helios.assets import Assets, EntryNotFoundError, Manifest


def test_renders_script_tag():
	path = f"scripts/main-{uuid4().hex}.js"
	assets = Assets(Manifest(scripts={"main": path}, styles={}), prefix="/assets/")

	tag = assets.script("main")

	assert_eq(tag, f'<script type="module" src="/assets/{path}"></script>')


def test_renders_style_tag():
	path = f"styles/main-{uuid4().hex}.css"
	assets = Assets(Manifest(scripts={}, styles={"main": path}), prefix="/assets/")

	tag = assets.style("main")

	assert_eq(tag, f'<link rel="stylesheet" href="/assets/{path}">')


def test_escapes_url_in_tag():
	assets = Assets(
		Manifest(scripts={}, styles={"main": "styles/main.css"}), prefix='/"/'
	)

	tag = assets.style("main")

	assert_eq(tag, '<link rel="stylesheet" href="/&#34;/styles/main.css">')


def test_script_raises_for_unknown_name():
	assets = Assets(Manifest(scripts={}, styles={}), prefix="/assets/")

	with assert_raises(EntryNotFoundError):
		assets.script(f"script-{uuid4().hex}")


def test_style_raises_for_unknown_name():
	assets = Assets(Manifest(scripts={}, styles={}), prefix="/assets/")

	with assert_raises(EntryNotFoundError):
		assets.style(f"style-{uuid4().hex}")
