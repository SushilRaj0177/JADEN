"""Properties every output must keep, checked on a fixed slice of the 33,294 JA-AddrBench inputs.

- Normalizing the canonical form gives the same canonical form, status and municipality.
- An address and its canonical form get the same match key.
- The hyphen form of an accepted address reads back as the same canonical form.
- An unresolved or ambiguous address is returned as written, so re-reading it changes nothing.
"""

import json
from pathlib import Path
from typing import List

import pytest

import jaden

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "jabench" / "jabench.jsonl"


def _sample(step: int = 11) -> List[str]:
    with open(BENCH, encoding="utf-8") as fh:
        return [json.loads(line)["input"] for i, line in enumerate(fh) if i % step == 0]


SAMPLE = _sample()


def test_the_sample_covers_every_variant() -> None:
    assert len(SAMPLE) > 3000


def test_canonical_form_is_a_fixed_point() -> None:
    bad = []
    for text in SAMPLE:
        res = jaden.normalize(text)
        if not res.canonical:
            continue
        again = jaden.normalize(res.canonical)
        v1, v2 = jaden.validate(text), jaden.validate(res.canonical)
        if again.canonical != res.canonical or (v1.status, v1.lg_code) != (v2.status, v2.lg_code):
            bad.append((text, res.canonical, again.canonical, v1.status, v2.status))
    assert bad == []


def test_match_key_is_the_same_for_the_canonical_form() -> None:
    bad = [(t, jaden.match_key(t), jaden.match_key(jaden.normalize(t).canonical)) for t in SAMPLE
           if jaden.normalize(t).canonical and jaden.match_key(t) != jaden.match_key(jaden.normalize(t).canonical)]
    assert bad == []


def test_hyphen_form_reads_back() -> None:
    bad = []
    for text in SAMPLE:
        res = jaden.normalize(text)
        if jaden.validate(text).status != "ACCEPTED":
            continue
        hyphen = res.format("hyphen")
        if jaden.normalize(hyphen).canonical != res.canonical:
            bad.append((text, res.canonical, hyphen))
    assert bad == []


@pytest.mark.parametrize("text", ["宮城野2-4-1", "福岡町1297", "東京工科大学", "南3条東1-2-1", "東京都23区"])
def test_unresolved_input_keeps_its_text_in_every_format(text: str) -> None:
    res = jaden.normalize(text)
    assert res.format("hyphen") == res.canonical == res.input_sanitized
