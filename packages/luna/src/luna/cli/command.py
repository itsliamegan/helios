from typing import Any

from luna.cli.runnable import Runnable
from luna.declarative import check_single_base


class Command(Runnable):
	def __init_subclass__(cls, **keywords: Any):
		super().__init_subclass__(**keywords)
		check_single_base(cls, Command, ValueError)
		cls.declare()
