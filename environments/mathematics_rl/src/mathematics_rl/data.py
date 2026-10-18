"""Pinned, lazy Hub loading and an equivalent offline NDJSON/Parquet input path."""

import hashlib
import json
import random
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .catalog import CATEGORIES, MODES, MODULES, contract_for, public_instruction

DATASET = "d0rj/mathematics_dataset"
REVISION = "d9f78d0665b3a13dad21c6830b9b358c8a25ae74"
GRADING_VERSION = "1"


@dataclass(frozen=True)
class Example:
    id: str
    question: str
    answer: str
    module: str
    category: str
    language: str
    kind: str
    revision: str
    content_hash: str

    @property
    def prompt(self) -> str:
        return public_instruction(contract_for(self.module, self.question), self.language) + (
            "\n\n" + self.question
        )


def categories_for(mode: str, categories: Iterable[str] = ()) -> tuple[str, ...]:
    if mode not in MODES:
        raise ValueError(f"Mode must be one of {tuple(MODES)}")
    selected = tuple(sorted(set(categories))) or MODES[mode]
    if not set(selected) <= set(MODES[mode]):
        raise ValueError(f"Categories {selected} do not belong to mode {mode!r}")
    return selected


def _local_rows(path: Path) -> Iterator[dict]:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        for batch in pq.ParquetFile(path).iter_batches(batch_size=2048):
            yield from batch.to_pylist()
    else:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError(f"Expected an object at {path}:{line_number}")
                    yield row


def examples(
    *,
    language: str = "ru",
    mode: str = "interpolate",
    categories: Iterable[str] = (),
    modules: Iterable[str] = (),
    revision: str = REVISION,
    source: str | None = None,
    seed: int = 42,
    shuffle_buffer: int = 0,
) -> Iterator[Example]:
    """Read lazily; the caller controls the number of tasks (e.g. Taskset.take).

    IDs include the position in the filtered source and content fingerprint, so
    repeated questions have distinct keys. They are stable for a fixed source,
    revision and filter configuration, independently of subsequent CLI selection.
    """
    if language not in ("ru", "en"):
        raise ValueError("language must be ru or en")
    selected_categories = categories_for(mode, categories)
    selected_modules = tuple(sorted(set(modules))) or MODULES
    if not set(selected_modules) <= set(MODULES):
        raise ValueError(f"Unknown modules: {set(selected_modules) - set(MODULES)}")
    if not 0 <= shuffle_buffer <= 100000:
        raise ValueError("shuffle_buffer must be between 0 and 100000")
    if not revision or (
        source is None
        and (len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision))
    ):
        raise ValueError("Pin the Hub dataset to a full 40-character commit hash")
    if source:
        rows = _local_rows(Path(source))
    else:
        from datasets import load_dataset

        rows = load_dataset(
            DATASET,
            "default",
            split=language,
            revision=revision,
            streaming=True,
            filters=[
                ("category", "in", list(selected_categories)),
                ("module", "in", list(selected_modules)),
            ],
        )

    def selected() -> Iterator[Example]:
        for index, row in enumerate(rows):
            if row.get("category") not in CATEGORIES or row.get("module") not in MODULES:
                raise ValueError(f"Invalid category/module in source row {index}")
            row_language = row.get("language", language)
            if row_language not in ("ru", "en"):
                raise ValueError(f"Invalid language in source row {index}")
            if (
                row_language != language
                or row["category"] not in selected_categories
                or (row["module"] not in selected_modules)
            ):
                continue
            question, answer = row.get("question"), row.get("answer")
            if (
                not isinstance(question, str)
                or not question.strip()
                or (not isinstance(answer, str) or not answer.strip())
            ):
                raise ValueError(f"Invalid question/answer in source row {index}")
            body = json.dumps(
                [language, row["category"], row["module"], question, answer],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            fingerprint = hashlib.sha256(body.encode()).hexdigest()
            origin = "local" if source else DATASET
            effective_revision = "local" if source and revision == REVISION else revision
            identity = json.dumps(
                [
                    origin,
                    effective_revision,
                    index,
                    selected_categories,
                    selected_modules,
                    fingerprint,
                ]
            )
            ident = hashlib.sha256(identity.encode()).hexdigest()
            yield Example(
                ident,
                question,
                answer,
                row["module"],
                row["category"],
                language,
                contract_for(row["module"], question).kind,
                effective_revision,
                fingerprint,
            )

    if not shuffle_buffer:
        yield from selected()
        return
    rng = random.Random(seed)
    buffer = []
    for item in selected():
        if len(buffer) < shuffle_buffer:
            buffer.append(item)
        else:
            position = rng.randrange(len(buffer))
            yield buffer[position]
            buffer[position] = item
    rng.shuffle(buffer)
    yield from buffer
