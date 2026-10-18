import hashlib
import json
import tomllib
from fractions import Fraction
from pathlib import Path

import pytest

from mathematics_rl.catalog import MODULES, contract_for
from mathematics_rl.grading import extract_answer, grade_answer
from mathematics_rl.parsing import ParseError, as_sympy, parse

FIXTURES = Path(__file__).parent / "fixtures"
ROWS = [
    json.loads(line)
    for path in sorted(FIXTURES.glob("generated_*.ndjson"))
    for line in path.read_text(encoding="utf-8").splitlines()
]


def grade(row, answer):
    return grade_answer(row["module"], row["question"], row["answer"], answer)


def wrong_answer(row):
    contract = contract_for(row["module"], row["question"])
    answer = row["answer"]
    if contract.kind == "boolean":
        return "False" if answer in ("True", "Истина") else "True"
    if contract.kind == "number":
        return str(Fraction(answer) + 1)
    if contract.kind == "roots":
        return str(max(Fraction(item) for item in answer.split(",")) + 1)
    if contract.kind == "ordered":
        return ", ".join(reversed(answer.split(", ")))
    if contract.kind == "clock":
        return "00:00" if not answer.startswith("12:00") else "00:01"
    if contract.kind in ("selection", "base"):
        return "0" if answer != "0" else "1"
    expression = as_sympy(parse(answer), positive=contract.positive)
    return str(expression + 1)


@pytest.mark.parametrize(
    "row",
    ROWS,
    ids=lambda row: f"{row['language']}/{row['category']}/{row['module']}/{row['fixture_index']}",
)
def test_generated_reference_and_wrong_answer(row):
    actual = grade(row, row["answer"])
    assert actual.status == "correct", (row, actual)
    assert grade(row, wrong_answer(row)).reward == 0, row


def test_fixture_provenance_and_module_documentation():
    provenance = tomllib.loads((FIXTURES / "provenance.toml").read_text(encoding="utf-8"))
    for language in ("en", "ru"):
        record = provenance[language]
        digest = hashlib.sha256((FIXTURES / record["file"]).read_bytes()).hexdigest()
        assert digest == record["sha256"]
    text = (FIXTURES.parents[1] / "MODULES.md").read_text(encoding="utf-8")
    assert all(f"`{module}`" in text for module in MODULES)


def test_complete_bilingual_catalog_and_categories():
    assert len(MODULES) == 70
    assert ROWS, "Generate the committed regression fixtures first"
    for language in ("en", "ru"):
        selected = [row for row in ROWS if row["language"] == language]
        assert {row["module"] for row in selected} == set(MODULES)
        assert {row["category"] for row in selected} == {
            "train-easy",
            "train-medium",
            "train-hard",
            "interpolate",
            "extrapolate",
        }
    assert {contract_for(row["module"], row["question"]).kind for row in ROWS} == {
        "number",
        "expression",
        "roots",
        "factors",
        "ordered",
        "selection",
        "boolean",
        "clock",
        "base",
        "expanded",
        "surd",
        "power",
    }


@pytest.mark.parametrize(
    "module,question,reference,answer",
    [
        ("arithmetic__div", "Divide 1 by 2.", "1/2", r"\boxed{\frac{2}{4}}"),
        ("arithmetic__div", "Divide 1 by 2.", "1/2", "0,5"),
        ("probability__swr_p_sequence", "Probability?", "1/2", "50%"),
        ("algebra__polynomial_roots", "Solve x**2-1=0.", "-1, 1", "{1, -1}"),
        ("numbers__is_prime", "Is 7 prime?", "True", r"\boxed{\text{Истина}}"),
        ("measurement__time", "What is the time?", "1:05 PM", "13:05"),
        ("measurement__time", "Который час?", "12:00 утра", "00:00"),
        ("numbers__base_conversion", "What is 10 (base 10) in base 16?", "a", "000A"),
        ("calculus__differentiate", "Differentiate x**3.", "3*x**2", "3x^{2}"),
        ("polynomials__compose", "Calculate.", "x**2-1", "(x-1)(x+1)"),
        ("polynomials__expand", "Expand.", "x**2-1", "-1 + x^2"),
        ("algebra__polynomial_roots", "Factor x**2-1.", "(x-1)*(x+1)", "(x+1)(x-1)"),
        (
            "polynomials__simplify_power",
            "Simplify, assuming x is positive.",
            "x**(-1/2)",
            r"1/\sqrt{x}",
        ),
        ("arithmetic__simplify_surd", "Simplify.", "2*sqrt(3)", r"2\sqrt{3}"),
    ],
)
def test_equivalent_answers(module, question, reference, answer):
    assert grade_answer(module, question, reference, answer).reward == 1


@pytest.mark.parametrize(
    "module,question,reference,answer",
    [
        ("arithmetic__add_or_sub", "Calculate 2+2.", "4", "2+2"),
        ("polynomials__expand", "Expand (x-1)*(x+1).", "x**2-1", "(x-1)*(x+1)"),
        ("polynomials__collect", "Collect x+x.", "2*x", "x+x"),
        ("algebra__polynomial_roots", "Factor x**2-1.", "(x-1)*(x+1)", "x**2-1"),
        ("algebra__polynomial_roots", "Solve x**2-1=0.", "-1, 1", "-1, 1, 1"),
        ("comparison__sort", "Sort 3, 2, 1.", "1, 2, 3", "3, 2, 1"),
        ("comparison__sort_composed", "Let a=1. Sort a,2.", "a, 2", "1, 2"),
        ("polynomials__simplify_power", "Simplify positive x.", "x**2", "x*x"),
        ("arithmetic__simplify_surd", "Simplify sqrt(12).", "2*sqrt(3)", "sqrt(12)"),
        ("numbers__base_conversion", "What is 4 (base 10) in base 2?", "100", "4"),
        ("measurement__time", "What is the time?", "1:05 PM", "1:05"),
        ("arithmetic__add_or_sub", "Calculate 2+2.", "4", "4 or 5"),
        ("arithmetic__add_or_sub", "Calculate 2+2.", "4", "14"),
        ("arithmetic__add_or_sub", "Calculate 2+2.", "4", "<think>\\boxed{4}"),
    ],
)
def test_wrong_answers_and_reward_shortcuts(module, question, reference, answer):
    assert grade_answer(module, question, reference, answer).reward == 0


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('echo unsafe')",
        "x.__class__",
        "[x for x in range(5)]",
        "lambda: 4",
        "sqrt(-1)",
        "1/0",
        "10**1000000000",
        "2**(2**100)",
        "x**(2**100)",
        "0**-1",
        "nan()",
        "(" * 100 + "1" + ")" * 100,
    ],
)
def test_unsafe_and_unbounded_expressions_fail(text):
    with pytest.raises((ParseError, ValueError)):
        as_sympy(parse(text))


def test_extraction_and_falsey_answers():
    assert extract_answer(r"Reasoning: \boxed{2}. Final: \boxed{\frac{1}{2}}") == r"\frac{1}{2}"
    assert extract_answer("<think>wrong 5</think>\nAnswer: 0") == "0"
    assert grade_answer("arithmetic__add_or_sub", "Compute.", "0", "0").reward == 1
    with pytest.raises(ParseError):
        extract_answer(r"\boxed{4}\n\boxed{")
    with pytest.raises(ParseError):
        extract_answer(" ")


def test_invalid_reference_is_distinct_from_model_failure():
    result = grade_answer("arithmetic__add_or_sub", "Compute.", "not a number", "0")
    assert result.status == "invalid_reference"


def test_large_exact_simple_power_and_polynomial_allocation_bounds():
    reference = "x**(1234567890123/98765432101)"
    assert (
        grade_answer(
            "polynomials__simplify_power", "Simplify positive x.", reference, reference
        ).reward
        == 1
    )
    for candidate in ("x**1000000000", "(a+b+c+d+e+f)**64", "(x**2-1)/(x-1)"):
        result = grade_answer("polynomials__compose", "Compute.", "x+1", candidate)
        assert result.reward == 0 and result.status == "parse_error"
