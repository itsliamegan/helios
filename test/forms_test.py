from lux.forms import rules, Field, Form

def test_validates_required_when_provided():
	form = Form([
		Field("title", [rules.required])
	])

	input, errs = form.validate({"title": "Intro"})

	assert input == {"title": "Intro"}
	assert errs == {}

def test_validates_required_when_missing():
	form = Form([
		Field("title", [rules.required])
	])

	input, errs = form.validate({})

	assert input == {}
	assert errs == {"title": ["must be provided"]}

def test_validates_required_when_empty():
	form = Form([
		Field("title", [rules.required])
	])

	input, errs = form.validate({"title": ""})

	assert input == {}
	assert errs == {"title": ["must not be empty"]}
