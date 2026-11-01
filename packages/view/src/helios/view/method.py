from markupsafe import Markup

from helios.http import Method


def method(name: str) -> Markup:
	"""Return the hidden field that makes a form send the method `name`.

	`name` must be the name of a `Method`, in upper case. Any other value
	raises `ValueError`.
	"""

	return Markup('<input type="hidden" name="_method" value="{}">').format(
		Method(name).value
	)
