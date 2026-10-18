import json
from itertools import islice

import pytest

from mathematics_rl.data import categories_for, examples


def write_rows(tmp_path, rows):
    target = tmp_path / "rows.ndjson"
    target.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return str(target)


def row(category="interpolate", **changes):
    return {
        "question": "What is 1+1?",
        "answer": "2",
        "category": category,
        "module": "arithmetic__add_or_sub",
        **changes,
    }


def test_language_and_train_eval_isolation(tmp_path):
    source = write_rows(
        tmp_path,
        [
            row(c, language=lang)
            for lang in ("ru", "en")
            for c in ("train-easy", "train-medium", "train-hard", "interpolate", "extrapolate")
        ],
    )
    for language in ("ru", "en"):
        loaded = list(examples(source=source, language=language, mode="train"))
        assert len(loaded) == 3
        assert {item.language for item in loaded} == {language}
        assert {item.category for item in loaded} == {"train-easy", "train-medium", "train-hard"}
        assert all(item.revision == "local" for item in loaded)
    assert len(list(examples(source=source, mode="extrapolate"))) == 1
    with pytest.raises(ValueError):
        categories_for("train", ["interpolate"])


def test_ids_duplicate_rows_selection_and_reference_privacy(tmp_path):
    source = write_rows(tmp_path, [row(answer="987654321"), row(answer="987654321")])
    first = list(examples(source=source))
    second = list(examples(source=source))
    assert first[0].id != first[1].id
    assert [item.id for item in first] == [item.id for item in second]
    assert first[0].content_hash == first[1].content_hash
    assert "987654321" not in first[0].prompt
    assert first[0].question in first[0].prompt


def test_buffer_shuffle_is_deterministic_and_does_not_change_keys(tmp_path):
    source = write_rows(tmp_path, [row(question=f"What is {i}+1?") for i in range(40)])
    original = list(examples(source=source))
    shuffled = list(examples(source=source, shuffle_buffer=5, seed=11))
    again = list(examples(source=source, shuffle_buffer=5, seed=11))
    assert {item.id for item in shuffled} == {item.id for item in original}
    assert shuffled == again
    assert shuffled != original
    assert len(list(islice(examples(source=source), 2))) == 2


@pytest.mark.parametrize(
    "options",
    [
        {"language": "fr"},
        {"modules": ["unknown"]},
        {"mode": "test"},
        {"shuffle_buffer": -1},
        {"revision": "main"},
    ],
)
def test_bad_configuration_fails_before_network(options):
    with pytest.raises(ValueError):
        next(examples(**options))


def test_bad_source_rows_are_loud(tmp_path):
    source = write_rows(tmp_path, [row(module="unknown")])
    with pytest.raises(ValueError):
        list(examples(source=source))
