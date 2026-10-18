"""Small bounded mathematical grammar. No eval, sympify, parse_expr or executable LaTeX."""

import math
import re
from dataclasses import dataclass

import sympy as sp

MAX_CHARS = 2048
MAX_TOKENS = 512
MAX_DEPTH = 32
MAX_INTEGER_BITS = 8192


class ParseError(ValueError):
    pass


@dataclass(frozen=True)
class Node:
    op: str
    args: tuple["Node", ...] = ()
    value: str = ""

    def symbols(self) -> set[str]:
        if self.op == "symbol":
            return {self.value}
        return set().union(*(child.symbols() for child in self.args))


def _group(text: str, position: int) -> tuple[str, int]:
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text) or text[position] != "{":
        raise ParseError("Expected a braced LaTeX argument")
    start = position + 1
    depth = 1
    position += 1
    while position < len(text):
        depth += (text[position] == "{") - (text[position] == "}")
        if depth > MAX_DEPTH:
            raise ParseError("LaTeX nesting limit")
        if depth == 0:
            return text[start:position], position + 1
        position += 1
    raise ParseError("Unclosed LaTeX argument")


def normalize_math(text: str, depth: int = 0) -> str:
    if depth > MAX_DEPTH or len(text) > MAX_CHARS:
        raise ParseError("Expression size/depth limit")
    text = text.strip().replace("−", "-").replace("–", "-").replace("×", "*")
    text = text.replace("÷", "/").replace("·", "*")
    text = re.sub(r"\\(?:left|right)\b", "", text)
    text = text.replace(r"\,", " ").replace(r"\!", " ").replace(r"\;", " ")
    text = text.replace(r"\cdot", "*").replace(r"\times", "*")
    text = text.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    result = []
    position = 0
    while position < len(text):
        if text.startswith(r"\frac", position):
            numerator, end = _group(text, position + 5)
            denominator, position = _group(text, end)
            result.append(
                f"(({normalize_math(numerator, depth + 1)})/"
                f"({normalize_math(denominator, depth + 1)}))"
            )
        elif text.startswith(r"\sqrt", position):
            value, position = _group(text, position + 5)
            result.append(f"sqrt({normalize_math(value, depth + 1)})")
        else:
            result.append(text[position])
            position += 1
    return "".join(result).replace("{", "(").replace("}", ")").replace("^", "**")


_TOKEN = re.compile(
    r"\s*(sqrt|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|"
    r"[a-zA-Z]|\*\*|[+*/()\-])"
)
_NUM = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")


class Parser:
    def __init__(self, text: str):
        text = normalize_math(text)
        self.tokens = []
        position = 0
        while position < len(text):
            if not text[position:].strip():
                break
            match = _TOKEN.match(text, position)
            if not match:
                raise ParseError("Unsupported token")
            self.tokens.append(match.group(1))
            position = match.end()
            if len(self.tokens) > MAX_TOKENS:
                raise ParseError("Token limit")
        self.index = 0
        self.depth = 0

    def peek(self) -> str:
        return self.tokens[self.index] if self.index < len(self.tokens) else ""

    def take(self) -> str:
        token = self.peek()
        self.index += 1
        return token

    def expression(self, minimum: int = 0) -> Node:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError("Expression nesting limit")
        token = self.take()
        if token in ("+", "-"):
            left = Node("neg" if token == "-" else "pos", (self.expression(30),))
        elif token == "(":
            left = self.expression()
            if self.take() != ")":
                raise ParseError("Unclosed parenthesis")
        elif token == "sqrt":
            if self.take() != "(":
                raise ParseError("sqrt needs parentheses")
            left = Node("sqrt", (self.expression(),))
            if self.take() != ")":
                raise ParseError("Unclosed sqrt")
        elif _NUM.fullmatch(token):
            if len(token) > 160:
                raise ParseError("Numeric literal limit")
            if "e" in token.lower() and abs(int(token.lower().split("e")[1])) > 512:
                raise ParseError("Scientific exponent limit")
            left = Node("number", value=token)
        elif re.fullmatch(r"[a-zA-Z]", token):
            left = Node("symbol", value=token)
        else:
            raise ParseError("Expected a mathematical atom")
        while True:
            token = self.peek()
            implicit = bool(
                token
                and (
                    token == "("
                    or token == "sqrt"
                    or _NUM.fullmatch(token)
                    or re.fullmatch(r"[a-zA-Z]", token)
                )
            )
            priority = {"+": 10, "-": 10, "*": 20, "/": 20, "**": 40}.get(token, -1)
            if implicit:
                priority = 20
                token = "*"
            if priority < minimum:
                break
            if not implicit:
                self.take()
            right = self.expression(priority if token == "**" else priority + 1)
            left = Node(
                {"+": "add", "-": "sub", "*": "mul", "/": "div", "**": "pow"}[token], (left, right)
            )
        self.depth -= 1
        return left

    def parse(self) -> Node:
        result = self.expression()
        if self.index != len(self.tokens):
            raise ParseError("Trailing tokens")
        return result


def parse(text: str) -> Node:
    return Parser(text).parse()


def as_sympy(node: Node, *, positive: bool = False) -> sp.Expr:
    if node.op == "number":
        return sp.Rational(node.value)
    if node.op == "symbol":
        return sp.Symbol(node.value, positive=True) if positive else sp.Symbol(node.value)
    values = [as_sympy(child, positive=positive) for child in node.args]
    if node.op == "neg":
        result = -values[0]
    elif node.op == "pos":
        result = values[0]
    elif node.op == "add":
        result = values[0] + values[1]
    elif node.op == "sub":
        result = values[0] - values[1]
    elif node.op == "mul":
        result = values[0] * values[1]
    elif node.op == "div":
        if values[1] == 0:
            raise ParseError("Division by zero")
        result = values[0] / values[1]
    elif node.op in ("pow", "sqrt"):
        base = values[0]
        exponent = sp.Rational(1, 2) if node.op == "sqrt" else values[1]
        if not exponent.is_Rational:
            raise ParseError("Power exponent limit")
        if max(int(sp.denom(exponent)).bit_length(), int(sp.numer(exponent)).bit_length()) > 256:
            raise ParseError("Power denominator limit")
        if base.is_number and base.is_Rational:
            if abs(exponent) > 4096:
                raise ParseError("Numeric power limit")
            bits = max(int(sp.numer(base)).bit_length(), int(sp.denom(base)).bit_length())
            if bits * max(1, abs(int(sp.numer(exponent)))) > MAX_INTEGER_BITS:
                raise ParseError("Power allocation limit")
        elif not (positive and node.args[0].op == "symbol") and abs(exponent) > 64:
            raise ParseError("Symbolic power limit")
        result = base**exponent
    else:
        raise ParseError("Unsupported expression")
    if result.has(sp.zoo, sp.oo, -sp.oo, sp.nan, sp.I):
        raise ParseError("Non-real or non-finite expression")
    if (
        isinstance(result, sp.Rational)
        and max(int(sp.numer(result)).bit_length(), int(sp.denom(result)).bit_length())
        > MAX_INTEGER_BITS
    ):
        raise ParseError("Integer allocation limit")
    if sp.count_ops(result) > 512:
        raise ParseError("Symbolic complexity limit")
    return result


def rational_node(node: Node) -> bool:
    if node.op == "number":
        return True
    if node.op in ("neg", "pos"):
        return rational_node(node.args[0])
    if node.op == "div":
        return all(rational_node(child) for child in node.args)
    return False


def polynomial_budget(node: Node) -> dict[str, int]:
    """Bound expansion before Poly can allocate a dense polynomial representation.

    Rational functions with variable denominators are deliberately not accepted
    as polynomials, even if automatic cancellation could hide their domain holes.
    """
    if rational_node(node):
        return {}
    if node.op == "symbol":
        return {node.value: 1}
    if node.op in ("pos", "neg"):
        return polynomial_budget(node.args[0])
    if node.op == "div" and rational_node(node.args[1]):
        return polynomial_budget(node.args[0])
    if node.op == "pow" and rational_node(node.args[1]):
        exponent = as_sympy(node.args[1])
        if not exponent.is_Integer or not 0 <= exponent <= 64:
            raise ParseError("Not a bounded polynomial power")
        result = {
            key: value * int(exponent) for key, value in polynomial_budget(node.args[0]).items()
        }
    elif node.op in ("add", "sub", "mul"):
        left, right = (polynomial_budget(child) for child in node.args)
        result = {
            key: (
                left.get(key, 0) + right.get(key, 0)
                if node.op == "mul"
                else max(left.get(key, 0), right.get(key, 0))
            )
            for key in left.keys() | right.keys()
        }
    else:
        raise ParseError("Expected a rational-coefficient polynomial")
    if (
        any(value > 64 for value in result.values())
        or math.prod(value + 1 for value in result.values()) > 20000
    ):
        raise ParseError("Polynomial expansion budget")
    return result


def additive_terms(node: Node) -> list[Node]:
    if node.op in ("add", "sub"):
        return additive_terms(node.args[0]) + additive_terms(node.args[1])
    if node.op in ("neg", "pos"):
        return additive_terms(node.args[0])
    return [node]


def is_expanded(node: Node) -> bool:
    """Require one monomial per term before SymPy can combine or cancel terms."""
    keys = set()
    variables = sorted(as_sympy(node).free_symbols, key=str)
    for term in additive_terms(node):

        def monomial(part: Node) -> bool:
            if rational_node(part) or part.op == "symbol":
                return True
            if part.op in ("pos", "neg"):
                return monomial(part.args[0])
            if part.op in ("mul", "div"):
                if part.op == "div" and not rational_node(part.args[1]):
                    return False
                return all(monomial(child) for child in part.args)
            if part.op == "pow" and part.args[0].op == "symbol":
                power = as_sympy(part.args[1])
                return bool(power.is_Integer and 0 <= power <= 64)
            return False

        if not monomial(term):
            return False
        expression = as_sympy(term)
        if expression == 0:
            continue
        key = sp.Poly(expression, *variables).monoms()[0] if variables else ()
        if key in keys:
            return False
        keys.add(key)
    return True


def is_factored(node: Node) -> bool:
    """Every nonconstant factor must be linear; these tasks have rational roots."""
    if node.op in ("pos", "neg"):
        return is_factored(node.args[0])
    if rational_node(node):
        return True
    if node.op == "mul":
        return all(is_factored(child) for child in node.args)
    if node.op == "div":
        return rational_node(node.args[1]) and is_factored(node.args[0])
    if node.op == "pow":
        exponent = as_sympy(node.args[1])
        return bool(exponent.is_Integer and 1 <= exponent <= 64 and is_factored(node.args[0]))
    expression = as_sympy(node)
    return bool(
        len(expression.free_symbols) == 1
        and sp.Poly(expression).total_degree() == 1
        and is_expanded(node)
    )


def is_simple_power(node: Node) -> bool:
    if node.op == "symbol":
        return True
    if rational_node(node):
        return as_sympy(node) == 1
    if node.op == "pow":
        return node.args[0].op == "symbol" and rational_node(node.args[1])
    if node.op == "sqrt":
        return node.args[0].op == "symbol"
    if node.op == "div" and rational_node(node.args[0]) and as_sympy(node.args[0]) == 1:
        return is_simple_power(node.args[1])
    return False


def is_simple_surd(node: Node) -> bool:
    keys = set()
    for term in additive_terms(node):
        radicals = []

        def piece(part: Node, radicals=radicals) -> bool:
            if rational_node(part):
                return True
            if part.op in ("neg", "pos"):
                return piece(part.args[0])
            if part.op == "mul":
                return all(piece(child) for child in part.args)
            if part.op == "div":
                return rational_node(part.args[1]) and piece(part.args[0])
            if part.op == "sqrt" or (
                part.op == "pow"
                and rational_node(part.args[1])
                and as_sympy(part.args[1]) == sp.Rational(1, 2)
            ):
                value = as_sympy(part.args[0])
                if not value.is_Integer or value <= 1:
                    return False
                if any(exponent > 1 for exponent in sp.factorint(value).values()):
                    return False
                radicals.append(int(value))
                return len(radicals) <= 1
            return False

        if not piece(term):
            return False
        if as_sympy(term) == 0:
            continue
        key = tuple(radicals)
        if key in keys:
            return False
        keys.add(key)
    return True
