from typing import Any

from .field import Field
from .filter import Filter, Trim
from .steps import Steps


class Filters(Steps[Filter[Any]]):
	def apply(self, field: Field, value: Any) -> Any:
		item_filters = self.item.get(field.name, [])
		field_filters = self.field.get(field.name, [])
		if field.is_list:
			value = [chain(trimmed(field, item_filters), item) for item in value]
			return chain(field_filters, value)
		else:
			return chain(trimmed(field, field_filters), value)


def trimmed(field: Field, filters: list[Filter[Any]]) -> list[Filter[Any]]:
	if field.trimmed:
		return [Trim(), *filters]
	else:
		return filters


def chain(filters: list[Filter[Any]], value: Any) -> Any:
	for step in filters:
		value = step.apply(value)
	return value
