"""Builds the development sets for the calibrated resolver (no held-out test data is touched).

  train      a random sample of company addresses (National Tax Agency register): the scorer's
             weights are fitted on it; the town prior leaves each row's own company out
  calib      half of the care offices (by office number): temperature, thresholds and conformal
             quantiles are chosen on it
  devcheck   the other half: a development check of everything chosen on calib

Each address gives three inputs, as in the held-out protocol: the town part alone ('town only'),
prefecture + town part ('with prefecture') and prefecture + municipality + town part ('full'),
each with the organisation's name as side information.

Usage:
    python benchmarks/calibration/make_dev.py [--companies 120000] [--care-every 1] [--jobs 4]
"""

import argparse
import csv
import gzip
import hashlib
import io
import pickle
import random
import sys
import unicodedata
import zipfile
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
DATA = Path.home() / ".cache" / "jaden-realdata"
OUT = HERE / "data"

# (set, variant, text, side, truth5, leave_out_town_text)
Row = Tuple[str, str, str, str, str, Optional[str]]
_B: Any = None


def _init() -> None:
    global _B
    from candidates import CandidateBuilder
    _B = CandidateBuilder()


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace("ヶ", "ケ").replace("ヵ", "ケ")


def strip_head(address: str, pref: str, city: str) -> str:
    """The typed address without its prefecture and municipality, when it has them."""
    a = address.strip()
    if _fold(a).startswith(_fold(pref)):
        a = a[len(pref):]
    county_free = city.split("郡", 1)[-1]
    for head in (city, county_free, city.split("市", 1)[0] + "市" if "市" in city[:-1] else ""):
        if head and _fold(a).startswith(_fold(head)):
            return a[len(head):].lstrip()
    return a


def variants(set_name: str, pref: str, city: str, town_part: str, side: str, truth: str,
             leave: Optional[str]) -> Iterator[Row]:
    if not town_part.strip():
        return
    yield set_name, "town only", town_part, side, truth, leave
    yield set_name, "with prefecture", pref + town_part, side, truth, leave
    yield set_name, "full", pref + city + town_part, side, truth, leave


def company_rows(n: int, seed: int) -> List[Row]:
    zips = sorted((DATA / "companies").glob("*.zip"))
    rows = []
    with zipfile.ZipFile(zips[-1]) as z:
        name = next(i.filename for i in z.infolist() if i.filename.endswith(".csv"))
        with z.open(name) as fh:
            for r in csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline="")):
                if len(r) < 24 or r[23] != "1" or r[18] or not (r[9] and r[10] and r[11]):
                    continue
                rows.append((r[9], r[10], r[11], r[6], r[13] + r[14]))
    random.Random(seed).shuffle(rows)
    out: List[Row] = []
    for pref, city, street, cname, code5 in rows[:n]:
        out.extend(variants("train", pref, city, street, cname, code5, street))
    return out


def care_rows(every: int) -> List[Row]:
    out: List[Row] = []
    seen = set()
    n = 0
    for path in sorted((DATA / "care").glob("jigyosho_*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            for r in reader:
                if len(r) < 16 or not r[7].strip():
                    continue
                key = (r[15], r[7])
                if key in seen:                     # one office listed under several services
                    continue
                seen.add(key)
                n += 1
                if n % every:
                    continue
                half = "calib" if int(hashlib.md5(r[15].encode()).hexdigest(), 16) % 2 == 0 else "devcheck"
                town_part = strip_head(r[7], r[2], r[3])
                out.extend(variants(half, r[2], r[3], town_part, r[4], r[0][:5], None))
    return out


def work(batch: List[Row]) -> List[Dict[str, Any]]:
    from build_prior import town_of, _STATE, _init as prior_init
    from candidates import label_of
    if not _STATE:
        prior_init()
    out = []
    for set_name, variant, text, side, truth5, leave_street in batch:
        lg6 = next((lg for lg in _B.by_code if lg[:5] == truth5), None)
        if lg6 is None:
            continue                                  # a code that no longer exists
        leave = None
        if leave_street is not None:
            found = town_of(lg6, leave_street)
            leave = (lg6, found[0]) if found else (lg6, "")
        item = _B.build(text, side, leave_out=leave)
        item.label = label_of(item, truth5, _B.by_code)
        out.append({"set": set_name, "variant": variant, "text": text, "side": side, "truth": truth5,
                    "status": item.status, "candidates": item.candidates, "x": item.x, "g": item.g,
                    "label": item.label, "meta": item.meta})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--companies", type=int, default=120000)
    ap.add_argument("--care-every", type=int, default=1)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    rows = company_rows(args.companies, args.seed) + care_rows(args.care_every)
    print(f"{len(rows):,} inputs", file=sys.stderr)
    batches = [rows[i:i + 2000] for i in range(0, len(rows), 2000)]
    sets: Dict[str, List[Dict[str, Any]]] = {}
    with Pool(args.jobs, initializer=_init) as pool:
        for i, items in enumerate(pool.imap(work, batches), 1):
            for it in items:
                sets.setdefault(it["set"], []).append(it)
            if i % 20 == 0:
                print(f"  {i * 2000:,} / {len(rows):,}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, items in sets.items():
        with gzip.open(OUT / f"{name}.pkl.gz", "wb") as fh:
            pickle.dump(items, fh)
        print(f"{name}: {len(items):,} inputs", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
