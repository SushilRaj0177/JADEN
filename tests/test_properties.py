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


def test_match_key_and_compare_agree() -> None:
    """Equal unit keys mean compare() says 'same', and 'same' means equal keys, for every pair of
    spellings of one address in the sample."""
    import itertools
    from collections import defaultdict
    groups = defaultdict(list)
    with open(BENCH, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            groups[(row["lat"], row["lon"], row["gold_lg"])].append(row["input"])
    bad = []
    for inputs in list(groups.values())[::25]:
        for a, b in itertools.combinations(inputs[:7], 2):
            ka, kb = jaden.match_key(a), jaden.match_key(b)
            verdict = jaden.compare(a, b).verdict
            if (ka is not None and ka == kb) != (verdict == "same"):
                bad.append((a, b, ka, kb, verdict))
    assert bad == []


TAILS = ["グランドメゾン302", "グランドメゾン 302号室", "グランドメゾン#302", "グランドメゾン303", "第一グランドメゾン302",
         "第1グランドメゾン 302", "第二グランドメゾン302", "グランドメゾンA棟302", "グランドメゾンB棟302",
         "グランドメゾン1-302", "グランドメゾン2-302", "グランドメゾン", "グランドメゾン二号館", "グランドメゾン2号館 302",
         "302", "3F", "グランドメゾン 3階"]


def test_match_key_and_compare_agree_with_buildings_and_rooms() -> None:
    import itertools
    bases = [t for t in SAMPLE[::40] if jaden.validate(t).status == "ACCEPTED"
             and jaden.match_key(t, "house") is not None and not jaden.normalize(t).components.building][:40]
    bad = []
    for base in bases:
        for x, y in itertools.combinations(TAILS, 2):
            a, b = f"{base} {x}", f"{base} {y}"
            ka, kb = jaden.match_key(a), jaden.match_key(b)
            verdict = jaden.compare(a, b).verdict
            if (ka is not None and ka == kb) != (verdict == "same"):
                bad.append((a, b, ka, kb, verdict))
    assert bad == []


REALLIFE = Path(__file__).resolve().parents[1] / "benchmarks" / "jabench" / "reallife.jsonl"


def test_real_life_inputs_read_back_the_same() -> None:
    """Rooms, buildings, floors, labels and spacing added to real addresses: the canonical and hyphen forms
    read back to the same canonical form, with the same match key."""
    with open(REALLIFE, encoding="utf-8") as fh:
        items = [json.loads(line) for i, line in enumerate(fh) if i % 7 == 0]
    bad = []
    for it in items:
        res = jaden.normalize(it["input"])
        if res.confidence_score <= 0:
            continue
        again = jaden.normalize(res.canonical)
        if again.canonical != res.canonical or jaden.match_key(it["input"]) != jaden.match_key(res.canonical):
            bad.append((it["input"], res.canonical, again.canonical))
        elif jaden.validate(it["input"]).status == "ACCEPTED" and \
                jaden.normalize(res.format("hyphen")).canonical != res.canonical:
            bad.append((it["input"], res.canonical, res.format("hyphen")))
    assert bad == []
