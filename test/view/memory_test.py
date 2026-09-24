from luna.test.assertion import assert_eq

from helios.view import Engine, memory


def test_memory_reloads_changed_templates_when_reloading():
	templates = {"index": "Before"}
	engine = Engine(memory.Driver(templates), reload=True)

	templates["index"] = "After"

	assert_eq(engine.render("index"), "After")
