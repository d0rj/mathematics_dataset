# Grading contract, version 1

## Extraction and notation

Use the last `\boxed{...}` / `\fbox{...}` outside completed `<think>...</think>`
blocks, otherwise the last nonempty line, optionally prefixed `Answer:`,
`Final answer:` or `Ответ:`. An unclosed thinking block or final box fails; no
fallback to a convenient earlier answer. Extraction never searches for the gold
answer. A final code-fence delimiter is ignored. Only one final answer is accepted.

Supported notation: exact decimal/scientific literals, rational fractions,
single-letter variables, implicit multiplication, powers (`**` / `^`), `sqrt`,
braced LaTeX `\frac` / `\sqrt`. Unsupported notation is a parse error, not a
request to an LLM judge. Scalar numbers accept decimal commas and percentages.
List separators are commas or semicolons, so use decimal points inside lists.
Equations and assignments are not final values.

## Rules

| Kind | Rule |
| --- | --- |
| Number | Exact rational equality: `1/2`, `0.5`, `2/4` agree. `1+1` is not a computed final number. No float tolerance. |
| Expression | Exact polynomial equality in reference variables over rational coefficients; equivalent expanded or factored forms accepted when no form is required. |
| Roots / prime factors | All distinct values, no omissions, additions or duplicates; order irrelevant. |
| Ordered list | Same elements in the required order. |
| Selection | Exact numeric value or original named-value label. Choice labels are case-insensitive. |
| Boolean | `True/False`, `yes/no`, `Истина/Ложь`, `да/нет`, `верно/неверно`; not numeric `0/1`. |
| Clock | Exact minute of day with AM/PM, утра/вечера/ночи/дня, or 24-hour HH:MM. Durations are numbers. |
| Base numeral | Valid digits in the question's output base; normalize case and leading zeroes. |
| Factorization | Complete product of rational constants and linear factors, with positive integer multiplicities. An equivalent expanded quadratic is rejected. |
| Expanded / collected | One monomial per term, distinct exponent vectors; reject products of sums and duplicate terms before simplifying. |
| Simple surd | Collected rational/radical terms, one squarefree positive-integer radical per term; `sqrt(12)` is not simplified. |
| Simple power | One rational power of the positive variable, including simple reciprocal/square-root notation. Positivity applies only to this module. |

Composed comparisons explicitly require original named-value labels: if the
answer is `a, 2, b`, returning numeric expansions is outside the output protocol.
This preserves identity without re-solving arbitrary context definitions; it is
a format restriction, not a claim that a different numeric expansion is false.

Final question wording distinguishes factorization from root-finding within one
module, and numeric selection from boolean comparisons. Candidate output never
chooses its own checker. All 70 module names are supported; unknown names fail.

## Resource bounds and failures

The checker builds SymPy objects from its own grammar. It never executes model
output with `eval`, `sympify` or `parse_expr`. Limits: 65,536-character completion,
2,048-character expression, 512 tokens, 32 parser nesting levels, 160-character
numeric literal, 8,192-bit intermediate rational and bounded powers. Reject
arbitrary functions, attributes, imports, strings, non-real/non-finite values.
Polynomial degree/monomial budgets are checked before expansion; variable
denominators are rejected rather than silently cancelling domain holes. Compact
positive-variable powers allow large exact rational exponents with bounded bit
length, so legitimate simplified power answers are not truncated to small exponents.

Live rewards use a reusable spawned process. Default deadlines are 3 seconds
per reference validation and per candidate, configurable up to 30s; startup has
a separate 30s allowance. Kill and replace a timed-out worker; no SymPy thread
keeps running. Scoring is serialized within each evaluator; scale via independent
framework workers. Reference validation has a bounded 4,096-entry cache.

Invalid/timed-out references are source errors, surfaced as failed framework
tasks. Invalid candidates earn 0 (`parse_error`); candidate deadlines earn 0
(`grading_timeout`). Internal failures raise. Resource limits can reject otherwise
valid but excessively complicated notation; this is not an unrestricted symbolic
equivalence oracle. Reference acceptance does not prove every reference true.
