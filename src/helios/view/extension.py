from itertools import count

from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.parser import Parser


class RenderExtension(Extension):
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


def blank(body: list[nodes.Node]) -> bool:
	return all(
		isinstance(node, nodes.Output)
		and all(
			isinstance(item, nodes.TemplateData) and not item.data.strip()
			for item in node.nodes
		)
		for node in body
	)
