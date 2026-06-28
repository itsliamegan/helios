from datetime import datetime, UTC

def date(date: datetime) -> str:
	return date.strftime("%b %-d, %Y")

def elapsed(then: datetime, now: datetime = None) -> str:
	if now is None:
		now = datetime.now(UTC)
	diff = now - then
	if diff.days == 0:
		mins = diff.seconds / 60
		hours = diff.seconds / (60 * 60)
		if mins < 1:
			return "less than a minute ago"
		elif hours < 1:
			return f"{round(mins)} {pluralize("minute", round(mins))} ago"
		else:
			return f"{round(hours)} {pluralize("hour", round(hours))} ago"
	elif diff.days < 7:
		return f"{diff.days} {pluralize("day", diff.days)} ago"
	else:
		return date(then)

def pluralize(noun: str, count: int) -> str:
	if count == 1:
		return noun
	else:
		return noun + "s"
