import re

SEPARATORS = re.compile(r"[\W_]+")


def words(name: str) -> list[str]:
	result: list[str] = []
	for word in SEPARATORS.split(name):
		if word:
			result.append(word)

	return result


def sentence(name: str) -> str:
	text = " ".join(words(name))
	return text[:1].upper() + text[1:]


def title(name: str) -> str:
	return " ".join(word[:1].upper() + word[1:] for word in words(name))


def dash(name: str) -> str:
	return "-".join(words(name)).lower()


def count(number: int, singular: str, plural: str | None = None) -> str:
	if number == 1:
		return f"1 {singular}"
	elif plural is None:
		return f"{number} {singular}s"
	else:
		return f"{number} {plural}"
