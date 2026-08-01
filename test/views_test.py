from datetime import datetime

from helios.http import URL
from helios.views import helpers, Views

def test_renders_simple():
	views = Views({"index": "<h1>{{ title }}</h1>"})

	html = views.render("index", {"title": "Index"})

	assert html == "<h1>Index</h1>"

def test_renders_inherited():
	views = Views({
		"base": "<h1>{{ title }}</h1>{% block content %}{% endblock %}",
		"show": "{% extends \"base\" %}{% block content %}<p>An article.</p>{% endblock %}"
	})

	html = views.render("show", {"title": "Intro"})

	assert html == "<h1>Intro</h1><p>An article.</p>"

def test_formats_elapsed_seconds():
	then = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 0)
	now = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 25)

	assert helpers.elapsed(then, now) == "less than a minute ago"

def test_formats_elapsed_minutes():
	then = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 0)
	now = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 30, second = 0)

	assert helpers.elapsed(then, now) == "30 minutes ago"

def test_formats_elapsed_hours():
	then = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 0)
	now = datetime(year = 2025, month = 9, day = 1, hour = 14, minute = 10, second = 0)

	assert helpers.elapsed(then, now) == "2 hours ago"

def test_formats_elapsed_days():
	then = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 0)
	now = datetime(year = 2025, month = 9, day = 3, hour = 14, minute = 0, second = 0)

	assert helpers.elapsed(then, now) == "2 days ago"

def test_formats_then_if_elapsed_over_a_week():
	then = datetime(year = 2025, month = 9, day = 1, hour = 12, minute = 0, second = 0)
	now = datetime(year = 2025, month = 9, day = 8, hour = 12, minute = 0, second = 0)

	assert helpers.elapsed(then, now) == "Sep 1, 2025"

def test_formats_date():
	date = datetime(year = 2026, month = 4, day = 7)

	assert helpers.date(date) == "Apr 7, 2026"

def test_formats_url_with_breaks():
	url = URL("/posts/1354")

	assert str(helpers.url(url)) == "/<wbr>posts/<wbr>1354"
