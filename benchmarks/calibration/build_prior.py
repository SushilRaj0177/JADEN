"""Counts the active companies registered in each town: how common each town is, as a prior.

When an address names only a town that exists in many municipalities (錦町 is in 93), the share of
real addresses each of them holds is the natural starting belief. The National Tax Agency register
gives one: every active company with its municipality code and registered address. Each company
is assigned to the registered town its address starts with inside its own municipality (JADEN's
town matcher), and the companies of each (municipality, town) pair are counted.

Output (development data only; nothing from the held-out test set):
    benchmarks/calibration/data/town_prior.tsv.gz    lg_code  town_key  town_name  companies
    benchmarks/calibration/data/municipality_prior.tsv  lg_code  companies

Usage:
    python benchmarks/calibration/build_prior.py [--data ~/.cache/jaden-realdata] [--jobs 4]
"""

import argparse
import gzip
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE.parents[1] / "benchmarks" / "realdata"))

OUT = HERE / "data"
_STATE: Dict[str, object] = {}


def _init() -> None:
    from jaden.data.gazetteer import get_gazetteer
    from jaden.data.loader import get_registry
    _STATE["gaz"] = get_gazetteer()
    _STATE["lg6"] = {m.lg_code[:5]: m.lg_code for m in get_registry().list_municipalities()}


def town_of(lg6: str, street: str) -> Optional[Tuple[str, str]]:
    """(town key, registered name) of the town the street text starts with, inside one municipality."""
    from jaden.core.kanji_numerals import normalize_kanji_numerals_in_blocks
    from jaden.core.sanitizer import sanitize_address_text
    from jaden.core.townkey import town_key
    gaz = _STATE["gaz"]
    text = normalize_kanji_numerals_in_blocks(sanitize_address_text(street))
    m = gaz.match_town(lg6, text)  # type: ignore[attr-defined]
    if m is None:
        return None
    return town_key(m.entry.name), m.entry.name


def count(batch: List[Tuple[str, str, str]]) -> Tuple[Counter, Counter, Dict[Tuple[str, str], str], int]:
    if not _STATE:
        _init()
    towns: Counter = Counter()
    munis: Counter = Counter()
    names: Dict[Tuple[str, str], str] = {}
    unmatched = 0
    for code5, street, _ident in batch:
        lg6 = _STATE["lg6"].get(code5)  # type: ignore[attr-defined]
        if lg6 is None:
            continue
        munis[lg6] += 1
        found = town_of(lg6, street)
        if found is None:
            unmatched += 1
            continue
        towns[(lg6, found[0])] += 1
        names[(lg6, found[0])] = found[1]
    return towns, munis, names, unmatched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path.home() / ".cache" / "jaden-realdata")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    import evaluate_companies
    zips = sorted((args.data / "companies").glob("*.zip"))
    rows = [(truth, street, ident) for ident, _p, _c, street, truth, _postal in evaluate_companies.read_rows(zips[-1])]
    print(f"{len(rows):,} companies", file=sys.stderr)
    batches = [rows[i:i + 20000] for i in range(0, len(rows), 20000)]
    towns: Counter = Counter()
    munis: Counter = Counter()
    names: Dict[Tuple[str, str], str] = {}
    unmatched = 0
    with Pool(args.jobs, initializer=_init) as pool:
        for i, (t, m, n, u) in enumerate(pool.imap_unordered(count, batches), 1):
            towns.update(t)
            munis.update(m)
            names.update(n)
            unmatched += u
            if i % 25 == 0:
                print(f"  {i * 20000:,}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "town_prior.tsv.gz", "wt", encoding="utf-8") as fh:
        fh.write("lg_code\ttown_key\ttown_name\tcompanies\n")
        for (lg, key), n in sorted(towns.items()):
            fh.write(f"{lg}\t{key}\t{names[(lg, key)]}\t{n}\n")
    with open(OUT / "municipality_prior.tsv", "w", encoding="utf-8") as fh:
        fh.write("lg_code\tcompanies\n")
        for lg, n in sorted(munis.items()):
            fh.write(f"{lg}\t{n}\n")
    print(f"{len(towns):,} towns hold {sum(towns.values()):,} companies; {unmatched:,} addresses matched no "
          f"registered town; {len(munis):,} municipalities", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
