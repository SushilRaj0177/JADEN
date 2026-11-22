"""Calibrated resolution: every candidate municipality with a probability.

``validate`` answers only when the official registries leave one municipality. ``resolve`` goes
further for addresses that do not name their municipality (``錦町1番2号`` fits 93 places): it gives
each candidate a probability, learned from 5 million registered company addresses and calibrated
on care-office addresses, and answers the most likely one only when that probability clears a
threshold chosen for a 1% wrong-answer rate. It also returns a candidate set that holds the right
municipality 95% of the time on data like the calibration data (split conformal prediction).

The evidence for a candidate: how many companies are registered in that town there, whether the
town and the 丁目 exist there, what the rules decided, and, when given, whether the organisation's
name mentions the municipality or the prefecture. A "none of these" option keeps a single
candidate from being certain: the registry does not hold every local name.

The probabilities are calibrated for data like the development data (company and care-office
addresses). On a held-out set of 321,859 welfare-facility addresses the results are in
``benchmarks/heldout/results/``.
"""

import gzip
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .core.kanji_numerals import normalize_kanji_numerals_in_blocks
from .core.townkey import town_key

_DATA = Path(__file__).parent / "data"
MAX_CANDIDATES = 60
FEATURES = (
    "log_town_companies", "log_town_share", "log_muni_companies", "town_exact", "town_found",
    "chome_exists", "chome_unchecked", "rules_accepted", "muni_written", "muni_homonym",
    "name_mentions_muni", "name_mentions_pref",
)
_NAME_COLUMNS = (FEATURES.index("name_mentions_muni"), FEATURES.index("name_mentions_pref"))


@dataclass(frozen=True)
class RankedCandidate:
    lg_code: str
    name: str            # prefecture + municipality, e.g. '東京都千代田区'
    probability: float


@dataclass(frozen=True)
class Resolution:
    input: str
    side: str                                   # the organisation name used as evidence, if any
    input_type: str                             # 'town only', 'with prefecture' or 'full'
    rules_status: str                           # what validate() says
    answered: bool                              # the best candidate clears the threshold
    lg_code: Optional[str]                      # the answer, when answered
    name: Optional[str]
    probability: float                          # of the best candidate
    candidates: Tuple[RankedCandidate, ...]     # most likely first
    none_probability: float                     # that the right municipality is none of them
    candidate_set: Tuple[str, ...]              # 95% conformal set (codes)
    set_includes_none: bool                     # the set also allows 'none of these'
    threshold: float


@lru_cache(maxsize=1)
def _prior() -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    towns: Dict[Tuple[str, str], int] = {}
    munis: Dict[str, int] = {}
    with gzip.open(_DATA / "resolver_prior.tsv.gz", "rt", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            lg, key, n = line.rstrip("\n").split("\t")
            if key == "*":
                munis[lg] = int(n)
            else:
                towns[(lg, key)] = int(n)
    return towns, munis


@lru_cache(maxsize=1)
def _model() -> Dict[str, Any]:
    return json.loads((_DATA / "resolver_model.json").read_text(encoding="utf-8"))


_PREFECTURES = ("北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県",
                "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県",
                "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県",
                "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県",
                "宮崎県", "鹿児島県", "沖縄県")


def mentions_prefecture(prefecture: str, text: str) -> bool:
    """Whether ``text`` names the prefecture: '京都' inside '東京都' is Tokyo, not Kyoto."""
    stem = prefecture[:-1] if prefecture != "北海道" else prefecture
    for other in _PREFECTURES:
        if other != prefecture and stem in other:
            text = text.replace(other, "")
    return stem in text


def _stem(name: str) -> str:
    last = re.split(r"(?<=[市])", name)[-1] or name
    return re.sub(r"(市|区|町|村)$", "", last)


def candidate_features(engine: Any, text: str, side: str = "",
                       leave_out: Optional[Tuple[str, str]] = None) -> Dict[str, Any]:
    """Candidates and their evidence for one input (the same features the model was fitted on)."""
    gaz = engine.gazetteer
    registry = engine.registry
    towns, munis = _prior()
    res = engine.normalize(text)
    val = engine.validate(text)
    c = res.components
    status = val.status
    if status == "ACCEPTED" and val.lg_code:
        codes = [val.lg_code]
    elif status == "AMBIGUOUS":
        codes = [m.group(1) for m in (re.search(r"\((\d{6})\)", x) for x in val.ambiguous_candidates) if m]
    else:
        codes = []
    muni_written = bool(c.lg_code) and not c.municipality_inferred and not c.is_ambiguous
    deduced = any("deduced from the town" in n for n in res.notes)
    town_part = normalize_kanji_numerals_in_blocks(res.input_sanitized)
    if c.prefecture and town_part.startswith(c.prefecture):
        town_part = town_part[len(c.prefecture):]
    if not c.municipality_inferred and not c.is_ambiguous:
        ward = c.ward if c.ward and c.ward != c.city else ""
        for head in ((c.county or "") + (c.city or "") + ward, (c.city or "") + ward, c.city or ""):
            if head and town_part.startswith(head):
                town_part = town_part[len(head):]
                break
    side_n = unicodedata.normalize("NFKC", side or "")
    has_numbers = any(v is not None for v in (c.chome, c.ban, c.go, c.banchi, c.edaban, c.lot_number))
    rows = []
    for lg in codes:
        m = registry.get_municipality_by_code(lg)
        match = gaz.match_town(lg, town_part) if (m is not None and gaz is not None) else None
        key = town_key(match.entry.name) if match else None
        count = towns.get((lg, key), 0) if key else 0
        muni_count = munis.get(lg, 0)
        if leave_out and leave_out[0] == lg:
            muni_count = max(0, muni_count - 1)
            if key == leave_out[1]:
                count = max(0, count - 1)
        entry = match.entry if match else None
        chome = c.chome
        rows.append({
            "lg": lg, "count": count, "muni_count": muni_count,
            "town_exact": float(bool(match and match.exact)), "town_found": float(match is not None),
            "chome_exists": float(bool(entry and chome is not None and entry.chomes_known and chome in entry.chomes)),
            "chome_unchecked": float(bool(chome is not None and not (entry and entry.chomes_known))),
            "rules_accepted": float(status == "ACCEPTED"), "muni_written": float(muni_written),
            "muni_homonym": float(bool(m and town_part.startswith(m.name) and match is None)),
            "name_mentions_muni": float(bool(m and side_n and len(_stem(m.name)) >= 2 and _stem(m.name) in side_n)),
            "name_mentions_pref": float(bool(m and side_n and mentions_prefecture(m.prefecture_name, side_n))),
        })
    rows.sort(key=lambda r: (-r["muni_homonym"], -r["count"]))
    rows = rows[:MAX_CANDIDATES]
    total = sum(r["count"] for r in rows)
    x = [[math.log1p(r["count"]), math.log((r["count"] + 0.5) / (total + 0.5 * len(rows))), math.log1p(r["muni_count"]),
          r["town_exact"], r["town_found"], r["chome_exists"], r["chome_unchecked"], r["rules_accepted"],
          r["muni_written"], r["muni_homonym"], r["name_mentions_muni"], r["name_mentions_pref"]] for r in rows]
    g = [1.0, math.log1p(len(codes)), float(status == "ACCEPTED"), float(status == "AMBIGUOUS"),
         float(status not in ("ACCEPTED", "AMBIGUOUS")), float(muni_written), float(bool(c.town_verified)),
         float(has_numbers), float(deduced)]
    if muni_written:
        input_type = "full"
    elif c.prefecture and not c.prefecture_inferred:
        input_type = "with prefecture"
    else:
        input_type = "town only"
    return {"status": status, "candidates": [r["lg"] for r in rows], "x": x, "g": g, "input_type": input_type,
            "has_numbers": has_numbers}


def probabilities(spec: Dict[str, Any], x: List[List[float]], g: List[float],
                  use_name: bool) -> Tuple[List[float], float]:
    """P(each candidate) and P(none of them) under one fitted model."""
    t = spec["temperature"]
    scores = [sum(w * (0.0 if (j in _NAME_COLUMNS and not use_name) else v)
                  for j, (w, v) in enumerate(zip(spec["w"], row))) / t for row in x]
    none = sum(v * f for v, f in zip(spec["v"], g)) / t
    top = max(scores + [none])
    e = [math.exp(s - top) for s in scores]
    en = math.exp(none - top)
    z = sum(e) + en
    return [v / z for v in e], en / z


def resolve(address: str, name: str = "") -> Resolution:
    """Every candidate municipality of ``address`` with a calibrated probability.

    ``name`` is optional evidence: the organisation or facility at the address
    (``'練馬区立旭丘保育園'`` points to 練馬区). The answer is given when its probability clears the
    threshold chosen for a 1% wrong-answer rate on the calibration data.
    """
    from .core.text import as_text
    from .engine import get_engine
    engine = get_engine()
    address, name = as_text(address), as_text(name)
    feats = candidate_features(engine, address, name)
    use_name = bool(name)
    spec = _model()["models"]["address+name" if use_name else "address"]
    p, p_none = probabilities(spec, feats["x"], feats["g"], use_name)
    registry = engine.registry

    def label(lg: str) -> str:
        m = registry.get_municipality_by_code(lg)
        return f"{m.prefecture_name}{m.name}" if m else lg

    ranked = sorted((RankedCandidate(lg, label(lg), pi) for lg, pi in zip(feats["candidates"], p)),
                    key=lambda r: -r.probability)
    q = spec["conformal_qhat"][feats["input_type"]]
    best = ranked[0] if ranked else None
    # The model was fitted on addresses, which have block or lot numbers. Text without any ('大泉町立北小学校',
    # a bare '南部町') is ranked but not answered.
    answered = bool(best and best.probability >= spec["threshold"] and feats["has_numbers"])
    members = [r.lg_code for r in ranked if 1 - r.probability <= q]
    none_in = 1 - p_none <= q
    if best is not None and best.lg_code not in members and (answered or (not members and not none_in)):
        # Never an empty set, and never one without the answer given
        members.insert(0, best.lg_code)
    if not members and not none_in:
        none_in = True
    return Resolution(
        input=address, side=name, input_type=feats["input_type"], rules_status=feats["status"],
        answered=answered, lg_code=best.lg_code if answered and best else None,
        name=best.name if answered and best else None, probability=best.probability if best else 0.0,
        candidates=tuple(ranked), none_probability=p_none,
        candidate_set=tuple(members), set_includes_none=none_in, threshold=spec["threshold"])
