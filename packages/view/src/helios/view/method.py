from markupsafe import Markup

from helios.http import Method


def method(name: str) -> Markup:
	"""Generate a hidden field that a form includes to send a method other than `GET` or `POST`.

	`name` must be the uppercased name of a `Method`. Any other value raises
	`ValueError`.
	"""

	return Markup('<input type="hidden" name="_method" value="{}">').format(
		Method(name).value
	)
