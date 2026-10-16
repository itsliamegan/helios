def words(name: str) -> list[str]:
	return [word for word in name.split("_") if word]


def sentence(name: str) -> str:
	text = " ".join(words(name))
	return text[:1].upper() + text[1:]


def title(name: str) -> str:
	return " ".join(word[:1].upper() + word[1:] for word in words(name))


def dash(name: str) -> str:
	return "-".join(words(name))


def count(number: int, singular: str, plural: str | None = None) -> str:
	if number == 1:
		return f"1 {singular}"
	elif plural is None:
		return f"{number} {singular}s"
	else:
		return f"{number} {plural}"
