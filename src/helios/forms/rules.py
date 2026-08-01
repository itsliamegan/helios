from typing import Any

def required(val: Any) -> str | None:
	if val is None:
		return "must be provided"
	elif val == "":
		return "must not be empty"
	else:
		return None
