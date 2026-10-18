"""Generate small, versioned regression fixtures without using the checker under test.

Run separately with the translated checkout and a pinned original English checkout.
Generated questions obey the same 160/30-character limits as the released corpus.
"""

import argparse
import hashlib
import json
import os
import random
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--language", choices=("ru", "en"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-module", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261018)
    args = parser.parse_args()
    sys.path.insert(0, os.path.abspath(args.source_root))
    import numpy as np
    from sympy.core.random import seed as sympy_seed

    from mathematics_dataset.modules import modules

    def flatten(items, prefix=""):
        result = {}
        for name, value in items.items():
            key = f"{prefix}__{name}" if prefix else name
            if isinstance(value, dict):
                result.update(flatten(value, key))
            else:
                result[key] = value
        return result

    mappings = {}
    for level, category in enumerate(("train-easy", "train-medium", "train-hard")):

        def entropy(interval, level=level):
            width = (interval[1] - interval[0]) / 3
            return interval[0] + level * width, interval[0] + (level + 1) * width

        mappings[category] = flatten(modules.train(entropy))
    mappings["interpolate"] = flatten(modules.test())
    mappings["extrapolate"] = flatten(modules.test_extra())
    rows = []
    for category, mapping in mappings.items():
        for module, generate in sorted(mapping.items()):
            identity = f"{args.seed}:{category}:{module}"
            seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:4], "big")
            random.seed(seed)
            np.random.seed(seed)
            sympy_seed(seed)
            for sample_index in range(args.per_module):
                for _ in range(10000):
                    problem = generate()
                    question, answer = str(problem.question), str(problem.answer)
                    if len(question) <= 160 and len(answer) <= 30:
                        break
                else:
                    raise RuntimeError(f"Cannot sample {module}")
                if args.language == "ru":
                    answer = {"True": "Истина", "False": "Ложь"}.get(answer, answer)
                rows.append(
                    {
                        "question": question,
                        "answer": answer,
                        "category": category,
                        "module": module,
                        "language": args.language,
                        "generator_answer_type": type(problem.answer).__name__,
                        "fixture_seed": seed,
                        "fixture_index": sample_index,
                    }
                )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "language": args.language,
                "rows": len(rows),
                "modules": len({row["module"] for row in rows}),
                "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
