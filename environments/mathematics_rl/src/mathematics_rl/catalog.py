"""The complete 70-module catalog and the public, reference-independent task contract."""

import re
from dataclasses import dataclass
from typing import Literal

Kind = Literal[
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
]

_DOMAINS = {
    "algebra": "linear_1d linear_1d_composed linear_2d linear_2d_composed "
    "polynomial_roots polynomial_roots_big polynomial_roots_composed "
    "sequence_next_term sequence_nth_term",
    "arithmetic": "add_or_sub add_or_sub_big add_or_sub_in_base add_sub_multiple "
    "add_sub_multiple_longer div div_big mixed mixed_longer mul mul_big "
    "mul_div_multiple mul_div_multiple_longer nearest_integer_root simplify_surd",
    "calculus": "differentiate differentiate_composed",
    "comparison": "closest closest_composed closest_more kth_biggest kth_biggest_composed "
    "kth_biggest_more pair pair_composed sort sort_composed sort_more",
    "measurement": "conversion time",
    "numbers": "base_conversion div_remainder div_remainder_composed gcd gcd_composed "
    "is_factor is_factor_composed is_prime is_prime_composed lcm lcm_composed "
    "list_prime_factors list_prime_factors_composed place_value place_value_big "
    "place_value_composed round_number round_number_big round_number_composed",
    "polynomials": "add coefficient_named collect compose evaluate evaluate_composed "
    "expand simplify_power",
    "probability": "swr_p_level_set swr_p_level_set_more_samples swr_p_sequence "
    "swr_p_sequence_more_samples",
}
MODULES = tuple(
    sorted(f"{domain}__{name}" for domain, names in _DOMAINS.items() for name in names.split())
)
CATEGORIES = ("train-easy", "train-medium", "train-hard", "interpolate", "extrapolate")
MODES = {"train": CATEGORIES[:3], "interpolate": ("interpolate",), "extrapolate": ("extrapolate",)}


@dataclass(frozen=True)
class Contract:
    kind: Kind
    positive: bool = False


def contract_for(module: str, question: str) -> Contract:
    """Classify the final task from its module and wording, never from model output."""
    if module not in MODULES:
        raise ValueError(f"Unknown module: {module}")
    domain, name = module.split("__", 1)
    if domain == "algebra":
        if name.startswith("polynomial_roots"):
            # Context definitions can contain many sentences; the factor instruction is final.
            factor = re.search(
                r"(?:^|[.!?]\s+)(?:Factor(?:ise|ize)?|Разложите на множители)\b", question, re.I
            )
            return Contract("factors" if factor else "roots")
        return Contract("expression" if name == "sequence_nth_term" else "number")
    if domain == "arithmetic":
        return Contract({"add_or_sub_in_base": "base", "simplify_surd": "surd"}.get(name, "number"))
    if domain == "calculus":
        return Contract("expression")
    if domain == "comparison":
        if name.startswith("sort"):
            return Contract("ordered")
        # pair alternates numeric selection and true/false comparison questions.
        if name.startswith("pair"):
            selection = re.search(
                r"(?:Which is (?:bigger|greater|smaller)|"
                r"Что (?:больше|меньше)|Какое значение больше)\s*:",
                question,
                re.I,
            )
            return Contract("selection" if selection else "boolean")
        return Contract("selection")
    if domain == "measurement":
        if name == "time" and not re.search(
            r"(?:How many minutes|Сколько минут)\b", question, re.I
        ):
            return Contract("clock")
        return Contract("number")
    if domain == "numbers":
        if name.startswith(("is_factor", "is_prime")):
            return Contract("boolean")
        if name.startswith("list_prime_factors"):
            return Contract("roots")
        return Contract("base" if name == "base_conversion" else "number")
    if domain == "polynomials":
        if name in ("expand", "collect"):
            return Contract("expanded")
        if name == "simplify_power":
            return Contract("power", positive=True)
        if name in ("add", "compose"):
            return Contract("expression")
    return Contract("number")


def public_instruction(contract: Contract, language: str) -> str:
    """A complete output contract visible to the solver, without reference answers."""
    if language == "ru":
        common = (
            "Решите задачу. Последняя непустая строка должна содержать только ответ "
            "(можно в \\boxed{...}). Используйте точные числа, дроби и обычную математическую "
            "запись; не приводите уравнение или несколько альтернативных ответов. "
        )
        rules = {
            "number": "Верните вычисленное число или дробь, без невыполненных вычислений.",
            "roots": "Перечислите все различные значения через запятую; порядок не важен.",
            "ordered": "Перечислите элементы через запятую в требуемом порядке. "
            "Для именованных величин сохраните исходные буквенные обозначения.",
            "selection": "Верните выбранное значение или исходное буквенное обозначение. "
            "В вопросе с вариантами (a), (b), ... верните только букву варианта.",
            "boolean": "Верните Истина или Ложь.",
            "base": "Верните запись числа в требуемой системе счисления, без её основания.",
            "clock": "Верните время с указанием утра/вечера или в 24-часовом формате HH:MM.",
            "factors": "Разложите полностью на линейные множители над рациональными числами.",
            "expanded": "Верните раскрытый многочлен с приведёнными подобными членами.",
            "power": "Верните одну степень положительной переменной с рациональным показателем.",
            "surd": "Приведите подобные слагаемые и извлеките все квадратные множители из корней.",
            "expression": "Верните математическое выражение в указанных переменных.",
        }
    else:
        common = (
            "Solve the problem. The final nonempty line must contain only the answer "
            "(optionally in \\boxed{...}). Use exact numbers, fractions and standard mathematical "
            "notation; do not return an equation or alternative answers. "
        )
        rules = {
            "number": "Return a computed number or fraction, not an unevaluated calculation.",
            "roots": "List all distinct values separated by commas; order does not matter.",
            "ordered": "List the elements separated by commas in the requested order. "
            "Preserve original letter labels for named quantities.",
            "selection": "Return the selected value or its original letter label. "
            "For choices (a), (b), ... return only the choice letter.",
            "boolean": "Return True or False.",
            "base": "Return the numeral in the requested base, without a base annotation.",
            "clock": "Return the time with AM/PM, or as 24-hour HH:MM.",
            "factors": "Factor completely into linear factors over the rationals.",
            "expanded": "Return an expanded polynomial with like terms collected.",
            "power": "Return one power of the positive variable with a rational exponent.",
            "surd": "Collect like terms and extract all square factors from radicals.",
            "expression": "Return a mathematical expression in the specified variables.",
        }
    return common + rules[contract.kind]
