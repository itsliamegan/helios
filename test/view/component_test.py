from dataclasses import dataclass

from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view.attributes import Attributes
from helios.view.component import Component


@dataclass
class Chip(Component):
	template = "chip"

	name: str


@dataclass
class Link(Component):
	template = "link"
	accepts = {"target", "rel"}  # noqa: RUF012

	url: str
	new_tab: bool = False
	content: Markup = Markup("")
	attributes: Attributes = Attributes()


def test_keeps_dataclass_repr():
	chip = Chip("Travel")

	text = repr(chip)

	assert_eq(text, "Chip(name='Travel')")


def test_rejects_rendering_outside_a_view():
	chip = Chip("Travel")

	with assert_raises(RuntimeError) as raised:
		str(chip)

	assert_eq(
		str(raised.exception),
		"Chip was rendered outside a view; use engine.render(component)",
	)


def test_rejects_missing_arguments_from_python():
	with assert_raises(TypeError):
		Chip()  # ty: ignore[missing-argument]


def test_rejects_loose_attributes_from_python():
	with assert_raises(TypeError):
		Link("/", class_="pin-link")  # ty: ignore[unknown-argument]


def test_accepts_global_and_declared_attributes_from_python():
	attributes = Attributes(
		class_="pin-link",
		id="link",
		hidden=True,
		data_turbo_frame="modal",
		target="_top",
		rel="nofollow",
	)

	link = Link("/", attributes=attributes)

	assert link.attributes is attributes


def test_rejects_unknown_attributes_from_python():
	with assert_raises(TypeError) as raised:
		Link("/", attributes=Attributes(tabindex=0))

	assert_eq(str(raised.exception), 'Link does not accept the attribute "tabindex"')
