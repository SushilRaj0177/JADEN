"""Post-hoc: does the town prior leak the answers of the held-out tests?

The calibrated resolver's town prior counts every active corporation in the National Tax Agency register
(benchmarks/calibration/build_prior.py). Test facilities are often run by a corporation registered at the
facility's own address (a 医療法人 at its clinic, a 社会福祉法人 at its home), and that corporation adds
weight to the right municipality of exactly that test input.

This script
  1. keys every test facility by (municipality, registered town, every number in the address);
  2. finds the corporations with the same key, and subtracts them from the prior (town and municipality
     counts) into a reduced copy;
  3. rebuilds the resolver's inputs for the town-only test inputs with the reduced prior and scores them
     with the same model, next to the original items.

Matching by town and numbers (not by the exact text) catches 4丁目2番8号 against 4-2-8; it can also
remove a corporation at the same numbers in the same town that is not the facility's operator, which only
makes the check stricter.

Usage:
    python benchmarks/posthoc/leakage.py --test1 DIR1 --test2 DIR2 [--data ~/.cache/jaden-realdata] [--jobs 3]
"""

import argparse
import gzip
import json
import pickle
import re
import shutil
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
for p in ("src", "benchmarks/calibration", "benchmarks/heldout", "benchmarks/realdata"):
    sys.path.insert(0, str(ROOT / p))

Key = Tuple[str, str, str]
_ST: Dict[str, Any] = {}


def _init() -> None:
    import build_prior
    build_prior._init()
    _ST["bp"] = build_prior


def numbers(text: str) -> str:
    from jaden.core.kanji_numerals import normalize_kanji_numerals_in_blocks
    from jaden.core.sanitizer import sanitize_address_text
    return "-".join(re.findall(r"\d+", normalize_kanji_numerals_in_blocks(sanitize_address_text(text))))


def key_of(lg6: str, street: str) -> Optional[Key]:
    found = _ST["bp"].town_of(lg6, street)
    if found is None:
        return None
    return lg6, found[0], numbers(street)


def _test_keys(rows: List[Tuple[str, str]]) -> List[Optional[Key]]:
    if not _ST:
        _init()
    return [key_of(lg6, street) for lg6, street in rows]


def _init_hits(wanted: Set[Tuple[str, str]], keys: Set[Key]) -> None:
    _init()
    _ST["wanted"], _ST["keys"] = wanted, keys


def _company_hits(batch: List[Tuple[str, str]]) -> List[Key]:
    wanted, keys = _ST["wanted"], _ST["keys"]
    out = []
    lg6_of = _ST["bp"]._STATE["lg6"]
    for code5, street in batch:
        lg6 = lg6_of.get(code5)
        if lg6 is None or (lg6, numbers(street)) not in wanted:
            continue
        k = key_of(lg6, street)
        if k is not None and k in keys:
            out.append(k)
    return out


def test_rows(data: Path) -> List[Tuple[str, str]]:
    """(six-digit code, address after the municipality) for every facility of both tests."""
    import make_inputs as welfare
    from jaden.data.loader import get_registry
    by5 = {m.lg_code[:5]: m for m in get_registry().list_municipalities()}
    rows = []
    for r in welfare.rows(data / "welfare" / "P14-23_GML.zip"):
        m = by5.get(r["truth"])
        if m:
            rows.append((m.lg_code, r["address"]))
    sys.path.insert(0, str(ROOT / "benchmarks" / "heldout2"))
    import importlib
    med = importlib.import_module("make_inputs")
    if not hasattr(med, "strip_heads"):          # the welfare module of the same name was imported first
        del sys.modules["make_inputs"]
        sys.path.insert(0, str(ROOT / "benchmarks" / "heldout2"))
        med = importlib.import_module("make_inputs")
    for r in med.rows(data):
        m = by5.get(r["pref"].zfill(2) + r["muni"].zfill(3)) if len(r["muni"]) == 3 else None
        if m and r["address"]:
            heads = med.strip_heads(r["address"], m)
            if heads["town only"]:
                rows.append((m.lg_code, heads["town only"]))
    return rows


def chunks(items: List[Any], n: int) -> Iterator[List[Any]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test1", type=Path, required=True)
    ap.add_argument("--test2", type=Path, required=True)
    ap.add_argument("--data", type=Path, default=Path.home() / ".cache" / "jaden-realdata")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--work", type=Path, required=True, help="scratch folder for the reduced prior and items")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()

    rows = test_rows(args.data)
    with Pool(args.jobs, initializer=_init) as pool:
        tkeys = [k for part in pool.imap(_test_keys, chunks(rows, 5000)) for k in part]
    keys = {k for k in tkeys if k is not None}
    wanted = {(k[0], k[2]) for k in keys}
    print(f"{len(rows):,} test facilities, {len(keys):,} distinct keys", file=sys.stderr)

    import evaluate_companies
    zips = sorted((args.data / "companies").glob("*.zip"))
    comp = [(code5, street) for _i, _p, _c, street, code5, _post in evaluate_companies.read_rows(zips[-1])]
    hits: Counter = Counter()
    with Pool(args.jobs, initializer=_init_hits, initargs=(wanted, keys)) as pool:
        for part in pool.imap_unordered(_company_hits, chunks(comp, 20000)):
            hits.update(part)
    removed = sum(hits.values())
    facilities_hit = sum(1 for k in tkeys if k is not None and hits.get(k))
    print(f"{removed:,} corporations share a key with a test facility; {facilities_hit:,} facilities affected", file=sys.stderr)

    # reduced prior
    src = ROOT / "benchmarks" / "calibration" / "data"
    red = args.work / "prior_reduced"
    red.mkdir(parents=True, exist_ok=True)
    town_minus: Counter = Counter()
    muni_minus: Counter = Counter()
    for (lg6, tkey, _nums), n in hits.items():
        town_minus[(lg6, tkey)] += n
        muni_minus[lg6] += n
    with gzip.open(src / "town_prior.tsv.gz", "rt", encoding="utf-8") as fi, \
            gzip.open(red / "town_prior.tsv.gz", "wt", encoding="utf-8") as fo:
        fo.write(next(fi))
        for line in fi:
            lg, key, name, n = line.rstrip("\n").split("\t")
            left = int(n) - town_minus.get((lg, key), 0)
            if left > 0:
                fo.write(f"{lg}\t{key}\t{name}\t{left}\n")
    with open(src / "municipality_prior.tsv", encoding="utf-8") as fi, open(red / "municipality_prior.tsv", "w", encoding="utf-8") as fo:
        fo.write(next(fi))
        for line in fi:
            lg, n = line.split()
            fo.write(f"{lg}\t{max(0, int(n) - muni_minus.get(lg, 0))}\n")
    shutil.copy(src / "model.json", red / "model.json")

    # rebuild town-only items with the reduced prior and score both versions
    sys.path.insert(0, str(ROOT / "benchmarks" / "heldout2"))
    from evaluate_heldout import Model, Scorer, wilson
    spec = json.loads((src / "model.json").read_text(encoding="utf-8"))
    models = {"calibrated": Model(spec["models"]["address"], False),
              "calibrated + name": Model(spec["models"]["address+name"], True)}
    scorer = Scorer()
    lines = ["# Post-hoc: town-prior leakage check", "",
             f"Test facilities keyed by municipality, registered town and numbers: {len(keys):,} distinct keys "
             f"({len(rows):,} facilities of both tests). Corporations in the National Tax Agency register with "
             f"the same key: **{removed:,}**, sharing a key with **{facilities_hit:,}** test facilities. They are "
             "removed from the prior, and the town-only test inputs are rebuilt and scored again with the same "
             "model and threshold.", "",
             "| Test | Model | Prior | Right | Wrong | Wrong among answers (95% CI) |", "| :--- | :--- | :--- | ---: | ---: | :--- |"]
    result: Dict[str, Any] = {"keys": len(keys), "corporations_removed": removed, "facilities_affected": facilities_hit}
    for tname, path in (("test 1", args.test1 / "jaden_items.pkl.gz"), ("test 2", args.test2 / "items_final.pkl.gz")):
        with gzip.open(path, "rb") as fh:
            items = [it for it in pickle.load(fh)["items"] if it["variant"] == "town only" and it.get("known_truth", True)]
        if any("side" not in it for it in items):        # test 2's items do not store the facility name
            sides = {}
            for line in open(path.parent / "inputs.jsonl", encoding="utf-8"):
                r = json.loads(line)
                if r["variant"] == "town only":
                    sides[r["id"]] = r["side"]
            for it in items:
                it["side"] = sides.get(it["id"], "")
        reduced = rebuild(items, red, args.jobs)
        for mname, model in models.items():
            for pname, its in (("full", items), ("reduced", reduced)):
                right = wrong = 0
                for it in its:
                    if not it["candidates"]:
                        continue
                    p, _ = model.probs(it)
                    j = max(range(len(p)), key=p.__getitem__)
                    if p[j] >= model.tau:
                        ok = scorer.right(it["candidates"][j], it["truth"])
                        right += ok
                        wrong += not ok
                lo, hi = wilson(wrong, right + wrong)
                n = len(its)
                result.setdefault(tname, {}).setdefault(mname, {})[pname] = {"n": n, "right": right, "wrong": wrong}
                lines.append(f"| {tname} | {mname} | {pname} | {100 * right / n:.2f}% | {wrong:,} | "
                             f"{100 * wrong / max(1, right + wrong):.2f}% ({100 * lo:.2f}–{100 * hi:.2f}%) |")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "leakage.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "leakage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


_B: Any = None


def _init_builder(folder: str) -> None:
    global _B
    from candidates import CandidateBuilder, Prior
    _B = CandidateBuilder(Prior(Path(folder)))


def _rebuild(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from candidates import label_of
    out = []
    for it in batch:
        item = _B.build(it["input"], it.get("side", ""))
        new = dict(it)
        new.update({"status": item.status, "candidates": item.candidates, "x": item.x, "g": item.g,
                    "label": label_of(item, it["truth"], _B.by_code)})
        out.append(new)
    return out


def rebuild(items: List[Dict[str, Any]], folder: Path, jobs: int) -> List[Dict[str, Any]]:
    with Pool(jobs, initializer=_init_builder, initargs=(str(folder),)) as pool:
        return [x for part in pool.imap(_rebuild, chunks(items, 2000)) for x in part]


if __name__ == "__main__":
    raise SystemExit(main())
