from collections.abc import Callable, Iterator, Sequence
from itertools import count

from jinja2 import TemplateSyntaxError, nodes
from jinja2.ext import Extension
from jinja2.lexer import Token, TokenStream
from jinja2.parser import Parser
from markupsafe import Markup

from .rendering import current


class RenderExtension(Extension):
	"""Adds the `render` tag, which renders a component with its body as `content`.

	A blank body passes no `content`.
	"""

	tags = {"render"}
	counter = count()

	def parse(self, parser: Parser) -> nodes.Node:
		lineno = next(parser.stream).lineno
		call = parser.parse_expression()
		if not isinstance(call, nodes.Call):
			parser.fail("render expects a component call", lineno)
		body = parser.parse_statements(("name:endrender",), drop_needle=True)
		statements: list[nodes.Node] = []
		if not blank(body):
			variable = f"render_content_{next(self.counter)}"
			statements.append(
				nodes.AssignBlock(
					nodes.Name(variable, "store"),
					None,
					body,
				).set_lineno(lineno)
			)
			call.kwargs.append(nodes.Keyword("content", nodes.Name(variable, "load")))
		statements.append(nodes.Output([call]).set_lineno(lineno))
		return nodes.Scope(statements).set_lineno(lineno)


class LayoutExtension(Extension):
	"""Adds the layout and section tags. Disables Jinja's extends and block."""

	tags = {"layout", "section"}

	def filter_stream(self, stream: TokenStream) -> Iterator[Token]:
		previous = None
		for token in stream:
			opens_tag = previous is not None and previous.type == "block_begin"
			if opens_tag and token.type == "name" and token.value in DISABLED:
				raise TemplateSyntaxError(
					f"Encountered unknown tag '{token.value}'.",
					token.lineno,
					stream.name,
					stream.filename,
				)
			yield token
			previous = token

	def parse(self, parser: Parser) -> nodes.Node:
		tag = next(parser.stream)
		if tag.value == "layout":
			return self.parse_layout(parser, tag.lineno)
		else:
			return self.parse_section(parser, tag.lineno)

	def parse_layout(self, parser: Parser, lineno: int) -> nodes.Node:
		name = parser.parse_expression()
		if not literal(name):
			parser.fail("layout expects a literal string", lineno)
		call = self.call_method("set_layout", [name])
		return nodes.ExprStmt(call).set_lineno(lineno)

	def parse_section(self, parser: Parser, lineno: int) -> nodes.Node:
		name = parser.parse_expression()
		if not literal(name):
			parser.fail("section expects a literal string", lineno)
		body = parser.parse_statements(("name:endsection",), drop_needle=True)
		call = self.call_method("set_section", [name])
		return nodes.CallBlock(call, [], [], body).set_lineno(lineno)

	def set_layout(self, name: str):
		current.get().set_layout(name)

	def set_section(self, name: str, caller: Callable[[], str]) -> str:
		current.get().set_section(name, Markup(caller()))
		return ""


def literal(name: nodes.Expr) -> bool:
	return isinstance(name, nodes.Const) and isinstance(name.value, str)


def blank(body: Sequence[nodes.Node]) -> bool:
	return all(
		isinstance(node, nodes.Output)
		and all(
			isinstance(item, nodes.TemplateData) and not item.data.strip()
			for item in node.nodes
		)
		for node in body
	)


DISABLED = {"extends", "block"}
