from datetime import datetime
from typing import Any

from helios.database import JSON, Model

from ...token import Token


class Record(Model):
	table = "sessions"

	token: Token
	items: JSON[dict[str, Any]]
	last_active_at: datetime
