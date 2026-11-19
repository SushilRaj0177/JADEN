"""Candidates and their evidence: what the calibrated resolver scores.

For one input, JADEN's rules give one municipality (ACCEPTED), a list (AMBIGUOUS) or nothing.
Each candidate municipality gets a feature vector describing the evidence for it, and the input
gets a second vector describing the evidence that the answer is *none* of the candidates (the
registry does not hold every local name, so even a single candidate can be wrong):

  candidate features (FEATURES)                      'none of these' features (NONE_FEATURES)
  - how many companies are registered in the town    - how many candidates there are
    there (log), and its share among the candidates  - what JADEN's rules said (accepted,
  - how many companies the municipality holds (log)    ambiguous, rejected)
  - the town name matched in full                    - whether the municipality was written,
  - the 丁目 written exists there / cannot be checked    and whether the town was verified
  - JADEN's rules accepted this candidate            - whether the input had block numbers
  - the municipality was written in the text
  - the input names this municipality as a town elsewhere (栄町 the town vs 栄町 the municipality)
  - the side information (a facility name) mentions the municipality / the prefecture

Nothing here looks at an answer key: labels are attached by the callers.
"""

import gzip
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

FEATURES = (
    "log_town_companies", "log_town_share", "log_muni_companies", "town_exact", "town_found",
    "chome_exists", "chome_unchecked", "rules_accepted", "muni_written", "muni_homonym",
    "name_mentions_muni", "name_mentions_pref",
)
NONE_FEATURES = (
    "bias", "log_candidates", "rules_accepted", "rules_ambiguous", "rules_rejected", "muni_written",
    "town_verified", "has_numbers", "deduced_from_town",
)
MAX_CANDIDATES = 60
DATA = HERE / "data"


@dataclass
class Item:
    text: str
    status: str
    candidates: List[str]                 # six-digit codes
    x: List[List[float]]                  # one row per candidate
    g: List[float]                        # 'none of these'
    names: List[str] = field(default_factory=list)
    label: Optional[int] = None           # index of the right candidate, len(candidates) for none
    meta: Dict[str, Any] = field(default_factory=dict)


class Prior:
    """Company counts per (municipality, town) and per municipality, from build_prior.py."""

    def __init__(self, folder: Path = DATA) -> None:
        self.towns: Dict[Tuple[str, str], int] = {}
        with gzip.open(folder / "town_prior.tsv.gz", "rt", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                lg, key, _name, n = line.rstrip("\n").split("\t")
                self.towns[(lg, key)] = int(n)
        self.munis: Dict[str, int] = {}
        with open(folder / "municipality_prior.tsv", encoding="utf-8") as fh:
            next(fh)
            for line in fh:
                lg, n = line.split()
                self.munis[lg] = int(n)


def _stem(name: str) -> str:
    """'練馬区' -> '練馬', '札幌市中央区' -> '中央' (the part a facility name would mention)."""
    last = re.split(r"(?<=[市])", name)[-1] or name
    return re.sub(r"(市|区|町|村)$", "", last)


class CandidateBuilder:
    def __init__(self, prior: Optional[Prior] = None) -> None:
        from jaden.data.gazetteer import get_gazetteer
        from jaden.data.loader import get_registry
        from jaden.engine import AddressNormalizer
        self.engine = AddressNormalizer()
        self.gaz = get_gazetteer()
        self.registry = get_registry()
        self.prior = prior or Prior()
        self.by_code = {m.lg_code: m for m in self.registry.list_municipalities()}
        self.prefectures = sorted({m.prefecture_name for m in self.by_code.values()}, key=len, reverse=True)

    def _town_part(self, sanitized: str, res: Any) -> str:
        """The text after any written prefecture and municipality."""
        from jaden.core.kanji_numerals import normalize_kanji_numerals_in_blocks
        text = normalize_kanji_numerals_in_blocks(sanitized)
        c = res.components
        for head in (c.prefecture, ):
            if head and text.startswith(head):
                text = text[len(head):]
        if not c.municipality_inferred and not c.is_ambiguous:
            for head in ((c.county or "") + (c.city or "") + (c.ward if c.ward and c.ward != c.city else ""),
                         (c.city or "") + (c.ward if c.ward and c.ward != c.city else ""), c.city or ""):
                if head and text.startswith(head):
                    return text[len(head):]
        return text

    def build(self, text: str, side: str = "", leave_out: Optional[Tuple[str, str]] = None) -> Item:
        """Candidates and features for one input. ``leave_out`` = (lg_code, town_key) whose count
        includes this very row (a company address), so the prior does not see its own answer."""
        from jaden.core.townkey import town_key
        res = self.engine.normalize(text)
        val = self.engine.validate(text)
        c = res.components
        status = val.status
        if status == "ACCEPTED" and val.lg_code:
            codes = [val.lg_code]
        elif status == "AMBIGUOUS":
            codes = [re.search(r"\((\d{6})\)", x).group(1) for x in val.ambiguous_candidates if re.search(r"\((\d{6})\)", x)]
        else:
            codes = []
        muni_written = bool(c.lg_code) and not c.municipality_inferred and not c.is_ambiguous
        deduced = any("deduced from the town" in n for n in res.notes)
        town_part = self._town_part(res.input_sanitized, res)
        side_n = unicodedata.normalize("NFKC", side or "")
        has_numbers = any(v is not None for v in (c.chome, c.ban, c.go, c.banchi, c.edaban, c.lot_number))

        rows = []
        for lg in codes:
            m = self.by_code.get(lg)
            match = self.gaz.match_town(lg, town_part) if m is not None else None
            key = town_key(match.entry.name) if match else None
            count = self.prior.towns.get((lg, key), 0) if key else 0
            muni_count = self.prior.munis.get(lg, 0)
            if leave_out and leave_out[0] == lg:
                muni_count = max(0, muni_count - 1)
                if key == leave_out[1]:
                    count = max(0, count - 1)
            chome = c.chome
            entry = match.entry if match else None
            chome_exists = float(bool(entry and chome is not None and entry.chomes_known and chome in entry.chomes))
            chome_unchecked = float(bool(chome is not None and not (entry and entry.chomes_known)))
            homonym = float(bool(m and town_part.startswith(m.name) and match is None))
            rows.append({
                "lg": lg, "count": count, "muni_count": muni_count,
                "town_exact": float(bool(match and match.exact)), "town_found": float(match is not None),
                "chome_exists": chome_exists, "chome_unchecked": chome_unchecked,
                "rules_accepted": float(status == "ACCEPTED"), "muni_written": float(muni_written),
                "muni_homonym": homonym,
                "name_mentions_muni": float(bool(m and side_n and len(_stem(m.name)) >= 2 and _stem(m.name) in side_n)),
                "name_mentions_pref": float(bool(m and side_n and m.prefecture_name[:-1] in side_n)),
            })
        # Very long lists: keep the most common towns (the rest rarely matter, and cost time)
        rows.sort(key=lambda r: (-r["muni_homonym"], -r["count"]))
        pruned = len(rows) > MAX_CANDIDATES
        rows = rows[:MAX_CANDIDATES]
        total = sum(r["count"] for r in rows)
        x = []
        for r in rows:
            share = (r["count"] + 0.5) / (total + 0.5 * len(rows))
            x.append([math.log1p(r["count"]), math.log(share), math.log1p(r["muni_count"]), r["town_exact"],
                      r["town_found"], r["chome_exists"], r["chome_unchecked"], r["rules_accepted"],
                      r["muni_written"], r["muni_homonym"], r["name_mentions_muni"], r["name_mentions_pref"]])
        g = [1.0, math.log1p(len(codes)), float(status == "ACCEPTED"), float(status == "AMBIGUOUS"),
             float(status not in ("ACCEPTED", "AMBIGUOUS")), float(muni_written),
             float(bool(c.town_verified)), float(has_numbers), float(deduced)]
        return Item(text=text, status=status, candidates=[r["lg"] for r in rows], x=x, g=g,
                    meta={"pruned": pruned, "n_rules": len(codes)})


def label_of(item: Item, truth: str, by_code: Dict[str, Any]) -> int:
    """Index of the right candidate (the row's municipality, or a ward of the row's designated city)."""
    truth5 = truth[:5]
    t = next((m for lg, m in by_code.items() if lg[:5] == truth5), None)
    for i, lg in enumerate(item.candidates):
        if lg[:5] == truth5:
            return i
        m = by_code.get(lg)
        if t is not None and m is not None and t.entity_type == "designated_city" and m.ward and m.city == t.city \
                and m.prefecture_code == t.prefecture_code:
            return i
    return len(item.candidates)
