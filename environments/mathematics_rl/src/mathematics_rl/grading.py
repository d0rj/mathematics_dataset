"""Deterministic typed rewards, separated from model clients and Verifiers imports."""

import re
from dataclasses import asdict, dataclass

import sympy as sp

from .catalog import Contract, contract_for
from .parsing import (
    MAX_CHARS,
    ParseError,
    as_sympy,
    is_expanded,
    is_factored,
    is_simple_power,
    is_simple_surd,
    parse,
    polynomial_budget,
    rational_node,
)

MAX_COMPLETION = 65536


@dataclass(frozen=True)
class Grade:
    reward: float
    status: str
    kind: str
    extracted: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def extract_answer(completion: str) -> str:
    """Last box, otherwise last nonempty line. Never consult the reference answer."""
    if not isinstance(completion, str) or len(completion) > MAX_COMPLETION:
        raise ParseError("Completion size limit")
    if completion.count("<think>") != completion.count("</think>"):
        raise ParseError("Unfinished thinking block")
    completion = re.sub(r"<think>.*?</think>", "", completion, flags=re.S).strip()
    if "<think>" in completion or "</think>" in completion:
        raise ParseError("Malformed thinking block")
    boxes = list(re.finditer(r"\\(?:boxed|fbox)\s*\{", completion))
    if boxes:
        start = boxes[-1].end()
        depth = 1
        for position in range(start, len(completion)):
            depth += (completion[position] == "{") - (completion[position] == "}")
            if depth == 0:
                answer = completion[start:position].strip()
                break
        else:
            raise ParseError("Unclosed final box")
    else:
        lines = [line.strip() for line in completion.splitlines() if line.strip()]
        if lines and lines[-1] == "```":
            lines.pop()
        answer = lines[-1] if lines else ""
        answer = re.sub(r"^(?:final\s+answer|answer|ответ)\s*:\s*", "", answer, flags=re.I)
    answer = answer.strip().strip("$").strip()
    if answer.startswith(r"\(") and answer.endswith(r"\)"):
        answer = answer[2:-2].strip()
    if not answer or len(answer) > MAX_CHARS:
        raise ParseError("Empty or oversized answer")
    return answer


def _plain(text: str) -> str:
    text = text.strip().replace("−", "-")
    match = re.fullmatch(r"\\(?:text|mathrm)\{([^{}]+)\}", text)
    if match:
        text = match[1].strip()
    return text


def _number(text: str) -> sp.Rational:
    text = _plain(text)
    if re.fullmatch(r"[+-]?\d+,\d+", text):
        text = text.replace(",", ".")
    percentage = text.endswith("%")
    if percentage:
        text = text[:-1].removesuffix("\\")
    node = parse(text)
    if not rational_node(node):
        raise ParseError("Return a numeric value, not an unevaluated expression")
    value = as_sympy(node)
    if not value.is_Rational:
        raise ParseError("Expected a rational value")
    return value / 100 if percentage else value


def _items(text: str) -> list[str]:
    text = text.strip().replace(r"\left", "").replace(r"\right", "")
    text = text.replace(r"\{", "{").replace(r"\}", "}")
    if text and (text[0], text[-1]) in (("{", "}"), ("[", "]"), ("(", ")")):
        depth = 0
        for position, char in enumerate(text):
            depth += (char in ("(", "{", "[")) - (char in (")", "}", "]"))
            if depth == 0:
                if position == len(text) - 1:
                    text = text[1:-1]
                break
    output, start, depth = [], 0, 0
    for position, char in enumerate(text):
        depth += (char in ("(", "{", "[")) - (char in (")", "}", "]"))
        if depth < 0:
            raise ParseError("Malformed list")
        if char in ",;" and depth == 0:
            output.append(text[start:position].strip())
            start = position + 1
    output.append(text[start:].strip())
    if depth or not all(output) or len(output) > 64:
        raise ParseError("Malformed or oversized list")
    return output


_BOOLEANS = {
    "true": True,
    "false": False,
    "yes": True,
    "no": False,
    "истина": True,
    "ложь": False,
    "да": True,
    "нет": False,
    "верно": True,
    "неверно": False,
}


def _boolean(text: str) -> bool:
    text = _plain(text).lower().rstrip(".")
    if text not in _BOOLEANS:
        raise ParseError("Expected an explicit boolean")
    return _BOOLEANS[text]


def _clock(text: str) -> int:
    match = re.fullmatch(
        r"(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.|утра|вечера|ночи|дня)?", _plain(text).lower()
    )
    if not match:
        raise ParseError("Expected a clock time")
    hours, minutes = int(match[1]), int(match[2])
    if minutes > 59:
        raise ParseError("Invalid minutes")
    if match[3]:
        if not 1 <= hours <= 12:
            raise ParseError("Invalid 12-hour time")
        hours %= 12
        if match[3] in ("pm", "p.m.", "вечера", "дня"):
            hours += 12
    elif hours > 23:
        raise ParseError("Invalid 24-hour time")
    return hours * 60 + minutes


def _base(text: str, question: str) -> int:
    bases = re.findall(r"(?:base\s*[-:]?\s*|основан\w*\s+)(\d+)", question, re.I)
    if not bases or not 2 <= int(bases[-1]) <= 36:
        raise ParseError("Unknown output base")
    text = _plain(text).lower()
    if not re.fullmatch(r"[+-]?[0-9a-z]+", text) or len(text) > 256:
        raise ParseError("Expected a base numeral")
    base = int(bases[-1])
    if any(
        "0123456789abcdefghijklmnopqrstuvwxyz".index(char) >= base for char in text.lstrip("+-")
    ):
        raise ParseError("Digit outside the requested base")
    try:
        return int(text, base)
    except ValueError as error:
        raise ParseError("Digit outside the requested base") from error


def _equivalent(candidate: str, reference: str, contract: Contract) -> bool:
    predicted = parse(candidate)
    expected = parse(reference)
    if contract.kind in ("expression", "factors", "expanded"):
        polynomial_budget(predicted)
        polynomial_budget(expected)
    pred_value = as_sympy(predicted, positive=contract.positive)
    gold_value = as_sympy(expected, positive=contract.positive)
    if pred_value.free_symbols - gold_value.free_symbols:
        return False
    if contract.kind == "factors" and not is_factored(predicted):
        return False
    if contract.kind == "expanded" and not is_expanded(predicted):
        return False
    if contract.kind == "power" and not is_simple_power(predicted):
        return False
    if contract.kind == "surd" and not is_simple_surd(predicted):
        return False
    if contract.kind in ("expression", "factors", "expanded"):
        # Only rational-coefficient polynomials are expected in these modules.
        variables = sorted(pred_value.free_symbols | gold_value.free_symbols, key=str)
        if variables:
            return sp.Poly(pred_value - gold_value, *variables, domain=sp.QQ).is_zero
        return pred_value == gold_value
    if contract.kind == "power":
        return sp.powsimp(pred_value / gold_value, force=False) == 1
    return sp.simplify(pred_value - gold_value) == 0


def _compare(candidate: str, reference: str, contract: Contract, question: str) -> bool:
    if contract.kind == "boolean":
        return _boolean(candidate) == _boolean(reference)
    if contract.kind == "clock":
        return _clock(candidate) == _clock(reference)
    if contract.kind == "base":
        return _base(candidate, question) == _base(reference, question)
    if contract.kind == "number":
        return _number(candidate) == _number(reference)
    if contract.kind == "roots":
        gold = {_number(item) for item in _items(reference)}
        predicted = [_number(item) for item in _items(candidate)]
        return len(predicted) == len(set(predicted)) and set(predicted) == gold
    if contract.kind in ("ordered", "selection"):
        gold = _items(reference) if contract.kind == "ordered" else [reference]
        predicted = _items(candidate) if contract.kind == "ordered" else [candidate]
        if len(gold) != len(predicted):
            return False
        for actual, target in zip(predicted, gold, strict=True):
            if re.fullmatch(r"[a-zA-Z]", target):
                choice = bool(re.search(r"\([a-z]\)", question, re.I))
                if (_plain(actual).lower() if choice else _plain(actual)) != target:
                    return False
            elif _number(actual) != _number(target):
                return False
        return True
    return _equivalent(candidate, reference, contract)


def grade_answer(module: str, question: str, reference: str, completion: str) -> Grade:
    """Run inside a worker with a wall-clock deadline (see worker.py)."""
    contract = contract_for(module, question)
    try:
        if len(reference) > MAX_CHARS or not _compare(reference, reference, contract, question):
            return Grade(0.0, "invalid_reference", contract.kind)
    except (ValueError, TypeError, ArithmeticError, RecursionError, sp.PolynomialError):
        return Grade(0.0, "invalid_reference", contract.kind)
    try:
        answer = extract_answer(completion)
        correct = _compare(answer, reference, contract, question)
        return Grade(float(correct), "correct" if correct else "incorrect", contract.kind, answer)
    except (ValueError, TypeError, ArithmeticError, RecursionError, sp.PolynomialError):
        return Grade(0.0, "parse_error", contract.kind)
