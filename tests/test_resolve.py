"""Calibrated resolution (jaden.resolve)."""

import math
import sys
from pathlib import Path

import pytest

import jaden
from jaden.engine import get_engine
from jaden.resolve import candidate_features

ROOT = Path(__file__).resolve().parents[1]


def test_unique_town_is_answered_with_high_probability() -> None:
    r = jaden.resolve("芝公園4-2-8")
    assert r.answered and r.lg_code == "131032" and r.name == "東京都港区"
    assert r.probability > 0.99


def test_full_address_is_answered() -> None:
    r = jaden.resolve("東京都港区芝公園4-2-8")
    assert r.answered and r.lg_code == "131032" and r.input_type == "full"


@pytest.mark.parametrize("address", ["錦町1番2号", "栄町7-7", "南3条東1-2-1"])
def test_ambiguous_town_is_not_answered_but_ranked(address: str) -> None:
    r = jaden.resolve(address)
    assert not r.answered
    assert len(r.candidates) > 1
    probs = [c.probability for c in r.candidates]
    assert probs == sorted(probs, reverse=True)
    assert math.isclose(sum(probs) + r.none_probability, 1.0, abs_tol=1e-9)
    assert 1 <= len(r.candidate_set) <= len(r.candidates)
    assert r.candidate_set[0] == r.candidates[0].lg_code


def test_a_name_that_mentions_a_candidate_raises_its_probability() -> None:
    plain = {c.lg_code: c.probability for c in jaden.resolve("南3条東1-2-1").candidates}
    named = {c.lg_code: c.probability for c in jaden.resolve("南3条東1-2-1", "網走市立南小学校").candidates}
    abashiri = "012114"
    assert named[abashiri] > plain[abashiri]


def test_non_address_has_no_candidates() -> None:
    r = jaden.resolve("あいうえお")
    assert not r.answered and r.candidates == () and r.lg_code is None


@pytest.mark.parametrize("text, side", [
    ("錦町1番2号", ""), ("南3条東1-2-1", "網走市立南小学校"), ("東京都港区芝公園4-2-8", ""),
    ("北海道南3条東1-2-1", ""), ("栄町7-7", "栄町役場"), ("中央1-1", ""),
])
def test_library_features_match_the_research_code(text: str, side: str) -> None:
    """The probabilities resolve() returns are those the held-out test measured."""
    sys.path.insert(0, str(ROOT / "benchmarks" / "calibration"))
    from candidates import CandidateBuilder
    research = CandidateBuilder().build(text, side)
    library = candidate_features(get_engine(), text, side)
    assert library["candidates"] == research.candidates
    assert library["x"] == research.x
    assert library["g"] == research.g
    assert library["status"] == research.status
