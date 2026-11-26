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
from multiprocessing import Pool, get_context
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

    src = ROOT / "benchmarks" / "calibration" / "data"
    red = args.work / "prior_reduced"
    stats_path = red / "stats.json"
    if stats_path.exists():                       # the reduced prior from an earlier run of this script
        stats = json.loads(stats_path.read_text(encoding="utf-8"))
        print(f"reusing {red}", file=sys.stderr)
    else:
        stats = build_reduced_prior(args, src, red)
    run_scoring(args, src, red, stats)
    return 0


def build_reduced_prior(args: argparse.Namespace, src: Path, red: Path) -> Dict[str, int]:
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
    stats = {"facilities": len(rows), "keys": len(keys), "corporations_removed": removed, "facilities_affected": facilities_hit}
    (red / "stats.json").write_text(json.dumps(stats), encoding="utf-8")
    return stats


def town_only_records(path: Path) -> List[Dict[str, Any]]:
    """The town-only inputs of one test with only the fields needed to rebuild them."""
    with gzip.open(path, "rb") as fh:
        items = pickle.load(fh)["items"]
    recs = [{"id": it["id"], "input": it["input"], "side": it.get("side"), "truth": it["truth"]}
            for it in items if it["variant"] == "town only" and it.get("known_truth", True)]
    del items
    if any(r["side"] is None for r in recs):       # test 2's items do not store the facility name
        sides = {}
        for line in open(path.parent / "inputs.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r["variant"] == "town only":
                sides[r["id"]] = r["side"]
        for r in recs:
            r["side"] = sides.get(r["id"], "")
    return recs


def run_scoring(args: argparse.Namespace, src: Path, red: Path, stats: Dict[str, int]) -> None:
    from evaluate_heldout import wilson
    lines = ["# Post-hoc: town-prior leakage check", "",
             f"Test facilities keyed by municipality, registered town and numbers: {stats['keys']:,} distinct keys "
             f"({stats['facilities']:,} facilities of both tests). Corporations in the National Tax Agency register "
             f"with the same key: **{stats['corporations_removed']:,}**, sharing a key with "
             f"**{stats['facilities_affected']:,}** test facilities. They are removed from the prior, and every "
             "town-only test input is rebuilt with each prior and scored with the same model and threshold.", "",
             "Both priors are used with the current engine. For test 2 that is the engine the test ran (the full-prior rows reproduce its reported numbers exactly); for test 1 it is not: the engine has changed since test 1, partly through fixes found on test 1's own errors, so test 1's absolute numbers here are not test results. Only the difference between the two priors is the measurement.", "",
             "| Test | Model | Prior | Right | Wrong | Wrong among answers (95% CI) |", "| :--- | :--- | :--- | ---: | ---: | :--- |"]
    result: Dict[str, Any] = dict(stats)
    ctx = get_context("spawn")                     # fresh workers: nothing large is copied into them
    for tname, path in (("test 1", args.test1 / "jaden_items.pkl.gz"), ("test 2", args.test2 / "items_final.pkl.gz")):
        recs = town_only_records(path)
        tally: Dict[Tuple[str, str], List[int]] = {}
        for pname, folder in (("full", src), ("reduced", red)):
            with ctx.Pool(args.jobs, initializer=_init_scoring, initargs=(str(folder),), maxtasksperchild=50) as pool:
                for part in pool.imap_unordered(_score, chunks(recs, 2000)):
                    for mname, (r, w) in part.items():
                        acc = tally.setdefault((mname, pname), [0, 0])
                        acc[0] += r
                        acc[1] += w
            print(f"  {tname}, {pname} prior: done", file=sys.stderr, flush=True)
        n = len(recs)
        for mname in ("calibrated", "calibrated + name"):
            for pname in ("full", "reduced"):
                right, wrong = tally[(mname, pname)]
                lo, hi = wilson(wrong, right + wrong)
                result.setdefault(tname, {}).setdefault(mname, {})[pname] = {"n": n, "right": right, "wrong": wrong}
                lines.append(f"| {tname} | {mname} | {pname} | {100 * right / n:.2f}% | {wrong:,} | "
                             f"{100 * wrong / max(1, right + wrong):.2f}% ({100 * lo:.2f}–{100 * hi:.2f}%) |")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "leakage.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "leakage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


_W: Dict[str, Any] = {}


def _init_scoring(folder: str) -> None:
    for p in ("src", "benchmarks/calibration", "benchmarks/heldout"):
        sys.path.insert(0, str(ROOT / p))
    from candidates import CandidateBuilder, Prior
    from evaluate_heldout import Model, Scorer
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    _W["builder"] = CandidateBuilder(Prior(Path(folder)))
    _W["models"] = {"calibrated": Model(spec["models"]["address"], False),
                    "calibrated + name": Model(spec["models"]["address+name"], True)}
    _W["scorer"] = Scorer()


def _score(batch: List[Dict[str, Any]]) -> Dict[str, Tuple[int, int]]:
    """Rebuild each input with this worker's prior; count right and wrong answers at the threshold."""
    out = {m: [0, 0] for m in _W["models"]}
    for r in batch:
        item = _W["builder"].build(r["input"], r["side"] or "")
        if not item.candidates:
            continue
        it = {"x": item.x, "g": item.g}
        for mname, model in _W["models"].items():
            p, _ = model.probs(it)
            j = max(range(len(p)), key=p.__getitem__)
            if p[j] >= model.tau:
                ok = _W["scorer"].right(item.candidates[j], r["truth"])
                out[mname][0 if ok else 1] += 1
    return {m: (v[0], v[1]) for m, v in out.items()}


if __name__ == "__main__":
    raise SystemExit(main())
