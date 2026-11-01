from luna.test.assertion import assert_eq, assert_raises

from helios.view import form


def test_method_renders_hidden_method_field():
	assert_eq(
		str(form.method("DELETE")),
		'<input type="hidden" name="_method" value="DELETE">',
	)


def test_method_rejects_lower_case_name():
	with assert_raises(ValueError):
		form.method("delete")


def test_method_rejects_unsupported_method():
	with assert_raises(ValueError):
		form.method("CONNECT")
