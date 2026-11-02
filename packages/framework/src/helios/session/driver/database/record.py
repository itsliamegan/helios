from datetime import datetime

from helios.database import Model

from .items import Items
from .token import Token


class Record(Model):
	table = "sessions"

	token: Token
	items: Items
	last_active_at: datetime
