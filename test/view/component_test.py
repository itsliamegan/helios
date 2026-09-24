from jinja2 import UndefinedError
from luna.test.assertion import assert_eq, assert_raises
from markupsafe import Markup

from helios.view import Attributes, Component, Engine, Helpers, memory


class Chip(Component):
	template = "chip"

	name: str


class Link(Component):
	template = "link"
	accepts = {"target", "rel"}

	url: str
	new_tab: bool = False
	content: Markup = Markup("")
	attributes: Attributes = Attributes()


class Board(Component):
	template = "board"

	name: str
	owner: str
	user: str

	@property
	def owned(self) -> bool:
		return self.owner == self.user


class Row(Component):
	template = "row"

	names: list[str]


link_template = (
	'<a href="{{ url }}" {{ attributes.merge(class="external-link", '
	'target=new_tab and "_blank", rel=new_tab and "noopener") }}>'
	"{{ content }}</a>"
)


def test_represents_fields():
	chip = Chip(name="Travel")

	text = repr(chip)

	assert_eq(text, "Chip(name='Travel')")


def test_rejects_rendering_outside_a_view():
	chip = Chip(name="Travel")

	with assert_raises(RuntimeError) as raised:
		str(chip)

	assert_eq(str(raised.exception), "Chip was rendered outside a view")


def test_rejects_missing_arguments_from_python():
	with assert_raises(TypeError):
		Chip()  # ty: ignore[missing-argument]


def test_rejects_positional_arguments_from_python():
	with assert_raises(TypeError):
		Chip("Travel")  # ty: ignore[missing-argument, too-many-positional-arguments]


def test_collects_loose_keywords_into_attributes():
	link = Link(url="/", class_="pin-link", data_turbo_frame="modal")  # ty: ignore[unknown-argument]

	assert_eq(link.attributes.names(), {"class", "data-turbo-frame"})


def test_inherits_fields():
	class Badge(Chip):
		template = "badge"

		count: int = 0

	badge = Badge(name="Travel")

	assert_eq(repr(badge), "Badge(name='Travel', count=0)")


def test_accepts_global_and_declared_attributes_from_python():
	attributes = Attributes(
		class_="pin-link",
		id="link",
		hidden=True,
		data_turbo_frame="modal",
		target="_top",
		rel="nofollow",
	)

	link = Link(url="/", attributes=attributes)

	assert link.attributes is attributes


def test_rejects_unknown_attributes_from_python():
	with assert_raises(TypeError) as raised:
		Link(url="/", attributes=Attributes(tabindex=0))

	assert_eq(str(raised.exception), 'Link does not accept the attribute "tabindex"')


def test_renders_fields():
	engine = Engine(
		memory.Driver(
			{
				"index": "{{ Chip(name=name) }}",
				"chip": "<span>{{ name }}</span>",
			}
		),
		components=[Chip],
	)

	html = engine.render("index", {"name": "<b>"})

	assert_eq(html, "<span>&lt;b&gt;</span>")


def test_renders_globals_and_filters():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Chip(name="travel") }}',
				"chip": "{{ name | shout }} on {{ site }}",
			}
		),
		Helpers(
			filters={"shout": lambda text: text.upper()},
			globals={"site": "Cork"},
		),
		components=[Chip],
	)

	html = engine.render("index")

	assert_eq(html, "TRAVEL on Cork")


def test_hides_caller_assigns():
	engine = Engine(
		memory.Driver(
			{
				"index": "{{ Chip(name=name) }}",
				"chip": "{{ title }}",
			}
		),
		components=[Chip],
	)

	with assert_raises(UndefinedError):
		engine.render("index", {"name": "Travel", "title": "Boards"})


def test_renders_component_properties():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Board(name="Travel", owner="ada", user="ada") }}',
				"board": "{{ name }}{% if component.owned %} (yours){% endif %}",
			}
		),
		components=[Board],
	)

	html = engine.render("index")

	assert_eq(html, "Travel (yours)")


def test_renders_nested_components():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Row(names=["a", "b"]) }}',
				"row": "<ul>{% for name in names %}<li>{{ Chip(name=name) }}</li>{% endfor %}</ul>",
				"chip": "{{ name }}",
			}
		),
		components=[Chip, Row],
	)

	html = engine.render("index")

	assert_eq(html, "<ul><li>a</li><li>b</li></ul>")


def test_renders_components_as_strings_inside_a_render():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ describe(Chip(name="<b>")) }}',
				"chip": "<span>{{ name }}</span>",
			}
		),
		Helpers(globals={"describe": lambda chip: "Chip: " + str(chip)}),
		components=[Chip],
	)

	html = engine.render("index")

	assert_eq(html, "Chip: &lt;span&gt;&amp;lt;b&amp;gt;&lt;/span&gt;")


def test_engine_renders_components():
	engine = Engine(
		memory.Driver({"chip": "<span>{{ name }}</span>"}), components=[Chip]
	)
	chip = Chip(name="Travel")

	html = engine.render(chip)

	assert_eq(html, "<span>Travel</span>")
	with assert_raises(RuntimeError):
		str(chip)


def test_rejects_missing_arguments_from_templates():
	engine = Engine(
		memory.Driver({"index": "{{ Chip() }}", "chip": "{{ name }}"}),
		components=[Chip],
	)

	with assert_raises(TypeError):
		engine.render("index")


def test_rejects_positional_arguments_from_templates():
	engine = Engine(
		memory.Driver({"index": '{{ Chip("Travel") }}', "chip": "{{ name }}"}),
		components=[Chip],
	)

	with assert_raises(TypeError):
		engine.render("index")


def test_rejects_unknown_keywords_without_attributes_field():
	engine = Engine(
		memory.Driver(
			{"index": '{{ Chip(name="a", class="b") }}', "chip": "{{ name }}"}
		),
		components=[Chip],
	)

	with assert_raises(TypeError):
		engine.render("index")


def test_passes_attributes_through_from_templates():
	engine = Engine(
		memory.Driver(
			{
				"index": (
					'{{ Link(url="/pins/1", new_tab=True, class="pin-link", '
					'data_turbo_frame="modal", rel="nofollow") }}'
				),
				"link": link_template,
			}
		),
		components=[Link],
	)

	html = engine.render("index")

	assert_eq(
		html,
		'<a href="/pins/1" class="external-link pin-link" target="_blank" '
		'rel="nofollow" data-turbo-frame="modal"></a>',
	)


def test_passes_attributes_bag_from_templates():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Link(url="/", attributes=bag) }}',
				"link": link_template,
			}
		),
		components=[Link],
	)

	html = engine.render("index", {"bag": Attributes(id="home")})

	assert_eq(html, '<a href="/" class="external-link" id="home"></a>')


def test_rejects_unknown_attributes_from_templates():
	engine = Engine(
		memory.Driver(
			{"index": '{{ Link(url="/", tabindex=0) }}', "link": link_template}
		),
		components=[Link],
	)

	with assert_raises(TypeError) as raised:
		engine.render("index")

	assert_eq(str(raised.exception), 'Link does not accept the attribute "tabindex"')


def test_rejects_attributes_bag_with_loose_attributes():
	engine = Engine(
		memory.Driver(
			{
				"index": '{{ Link(url="/", attributes=bag, id="home") }}',
				"link": link_template,
			}
		),
		components=[Link],
	)

	with assert_raises(TypeError):
		engine.render("index", {"bag": Attributes(class_="pin-link")})


def test_rejects_components_with_the_same_name():
	class Chip(Component):
		template = "chip"

	driver = memory.Driver({"chip": ""})

	with assert_raises(ValueError):
		Engine(driver, components=[Chip, globals()["Chip"]])


def test_rejects_components_named_like_helper_globals():
	driver = memory.Driver({"chip": ""})

	with assert_raises(ValueError):
		Engine(driver, Helpers(globals={"Chip": "chip"}), components=[Chip])


def test_rejects_components_with_missing_templates():
	driver = memory.Driver({"index": ""})

	with assert_raises(ValueError):
		Engine(driver, components=[Chip])


def test_rejects_accepts_without_attributes_field():
	with assert_raises(ValueError):

		class Button(Component):
			template = "button"
			accepts = {"type"}


def test_rejects_accepts_that_name_a_field():
	with assert_raises(ValueError):

		class Button(Component):
			template = "button"
			accepts = {"form-action"}

			form_action: str
			attributes: Attributes = Attributes()


def test_rejects_fields_named_component():
	with assert_raises(ValueError):

		class Wrapper(Component):
			template = "wrapper"

			component: str


def test_rejects_fields_named_like_component_members():
	with assert_raises(ValueError):

		class Wrapper(Component):
			template: str = "wrapper"  # ty: ignore[invalid-attribute-override]


def test_rejects_mutable_defaults():
	with assert_raises(ValueError):

		class Row(Component):
			template = "row"

			names: list[str] = []
