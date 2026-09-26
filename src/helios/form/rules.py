from typing import Any

from .field import Field
from .key import Key
from .rule import Rule, RuleError
from .steps import Steps


class Rules(Steps[Rule[Any]]):
	def check(self, field: Field, value: Any):
		if field.is_list:
			for item in value:
				run(self.item.get(field.name, []), field.name, True, item)

		run(self.field.get(field.name, []), field.name, False, value)


def run(rules: list[Rule[Any]], name: str, item: bool, value: Any):
	for rule in rules:
		try:
			rule.check(value)
		except RuleError as error:
			key = Key(name, item=item, rest=rule.name)
			raise RuleError(error.message, key) from error
