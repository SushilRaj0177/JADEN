"""Post-hoc analyses behind the numbers in the paper's analysis sections, written out so that each can be
checked. Nothing here changes a pre-registered result.

  1. Forced answers: how often the calibrated resolver's top candidate is wrong when it must answer every
     town-only input that has candidates.
  2. Where the calibrated resolver is wrong (town only, at the threshold): the right municipality not among
     the candidates, against a ranking error among them.
  3. Inputs that start with a municipality name (富岡町1-56-26-2): answered and wrong at the threshold, on
     the care-office development check and on both tests.
  4. Language models (test 1): the comparisons the paper's systems mix, separated: choosing with and
     without the confidence filter, proposing with verification only, with confidence only, with both;
     and how many right answers each filter throws away.
  5. Projection: the calibrated resolver plus the verified language-model proposals on the whole test.
  6. Intervals that respect repeated addresses: wrong-answer rates with a cluster bootstrap over identical
     input texts, next to the Wilson intervals that treat every input as independent.
  7. Sizes quoted in the paper (training inputs, calibration split).

Usage:
    python benchmarks/posthoc/analysis.py --test1 DIR1 --test2 DIR2
      DIR1 holds jaden_items.pkl.gz and the llm_*.jsonl files of test 1; DIR2 holds items_final.pkl.gz
"""

import argparse
import gzip
import json
import pickle
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "calibration"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))

from evaluate_heldout import Model, Scorer, wilson  # noqa: E402

CONFIDENCE = 80


def load_items(path: Path, town_only: bool = False) -> List[Dict[str, Any]]:
    with gzip.open(path, "rb") as fh:
        blob = pickle.load(fh)
    items = blob["items"] if isinstance(blob, dict) else blob
    return [it for it in items if it["variant"] == "town only"] if town_only else items


def top(model: Model, it: Dict[str, Any]) -> Tuple[float, int]:
    p, _ = model.probs(it)
    j = max(range(len(p)), key=p.__getitem__)
    return p[j], j


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.2f}%" if n else "–"


def cluster_ci(outcomes: List[Tuple[str, bool]], reps: int = 1000, seed: int = 7) -> Tuple[float, float]:
    """95% percentile interval of the wrong-answer rate, resampling clusters of identical input texts."""
    clusters: Dict[str, List[int]] = defaultdict(lambda: [0, 0])
    for key, wrong in outcomes:
        clusters[key][0] += 1
        clusters[key][1] += wrong
    sizes = [(n, w) for n, w in clusters.values()]
    rng = random.Random(seed)
    m = len(sizes)
    rates = []
    for _ in range(reps):
        n = w = 0
        for _ in range(m):
            a, b = sizes[rng.randrange(m)]
            n += a
            w += b
        rates.append(w / n if n else 0.0)
    rates.sort()
    return rates[int(0.025 * reps)], rates[int(0.975 * reps) - 1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test1", type=Path, required=True)
    ap.add_argument("--test2", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    from jaden.data.loader import get_registry
    muni_names = sorted({n for m in get_registry().list_municipalities() for n in (m.name, m.city) if n},
                        key=len, reverse=True)
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    models = {"calibrated": Model(spec["models"]["address"], False),
              "calibrated + name": Model(spec["models"]["address+name"], True)}
    scorer = Scorer()
    t1 = load_items(args.test1 / "jaden_items.pkl.gz", town_only=True)
    t2 = load_items(args.test2 / "items_final.pkl.gz", town_only=True)
    dev = load_items(ROOT / "benchmarks" / "calibration" / "data" / "devcheck.pkl.gz", town_only=True)
    for it in dev:
        it.setdefault("known_truth", True)
        it.setdefault("input", it.get("text", ""))
    res: Dict[str, Any] = {}
    lines = ["# Post-hoc analyses", "", "Computed after both tests from their stored outputs; see the docstring of "
             "`analysis.py` for what each section is. No pre-registered number changes.", ""]

    def town(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [it for it in items if it["variant"] == "town only" and it.get("known_truth", True)]

    # 1 and 2
    lines += ["## 1–2. Forced answers and where the calibrated resolver is wrong (town only)", "",
              "| Test | Model | With candidates | Forced: wrong | At threshold: answered | wrong | truth not among candidates | ranking error |",
              "| :--- | :--- | ---: | :--- | ---: | ---: | ---: | ---: |"]
    for tname, items in (("test 1", town(t1)), ("test 2", town(t2))):
        for mname, model in models.items():
            withc = forced_wrong = ans = wrong = missing = ranking = 0
            for it in items:
                if not it["candidates"]:
                    continue
                withc += 1
                p, j = top(model, it)
                ok = scorer.right(it["candidates"][j], it["truth"])
                forced_wrong += not ok
                if p >= model.tau:
                    ans += 1
                    if not ok:
                        wrong += 1
                        truth_in = 0 <= it["label"] < len(it["candidates"])
                        missing += not truth_in
                        ranking += truth_in
            res.setdefault("forced", {})[f"{tname} {mname}"] = {"with_candidates": withc, "forced_wrong": forced_wrong,
                                                                 "answered": ans, "wrong": wrong, "truth_missing": missing,
                                                                 "ranking": ranking}
            lines.append(f"| {tname} | {mname} | {withc:,} | {forced_wrong:,} ({pct(forced_wrong, withc)}) | {ans:,} | "
                         f"{wrong:,} | {missing:,} | {ranking:,} |")

    # 3
    lines += ["", "## 3. Town-only inputs that start with a municipality name (calibrated, at the threshold)", "",
              "| Data | Such inputs | Answered | Wrong | Wrong among answers |", "| :--- | ---: | ---: | ---: | ---: |"]
    model = models["calibrated"]
    for dname, items in (("care offices (development check)", town(dev)), ("test 1", town(t1)), ("test 2", town(t2))):
        n = ans = wrong = 0
        for it in items:
            text = it.get("input") or it.get("text") or ""
            if not any(text.startswith(nm) for nm in muni_names) or not it["candidates"]:
                continue
            n += 1
            p, j = top(model, it)
            if p >= model.tau:
                ans += 1
                wrong += not scorer.right(it["candidates"][j], it["truth"])
        res.setdefault("starts_with_municipality", {})[dname] = {"inputs": n, "answered": ans, "wrong": wrong}
        lines.append(f"| {dname} | {n:,} | {ans:,} | {wrong:,} | {pct(wrong, ans)} |")

    # 4 and 5
    by_id = {it["id"]: it for it in t1}
    llm_dir = args.test1

    def answers(name: str) -> List[Dict[str, Any]]:
        path = llm_dir / name
        return [json.loads(line) for line in open(path, encoding="utf-8")] if path.exists() else []

    lines += ["", "## 4. Language models on test 1, filters separated", "",
              "Kept = answers that survive the filter; discarded right = right answers the filter throws away.", "",
              "| System | Sample | Filter | Kept | Wrong among kept (95% CI) | Right answers discarded |",
              "| :--- | :--- | :--- | ---: | :--- | ---: |"]
    runs = (("haiku chooses", "llm_choose.jsonl", "remainder", True),
            ("haiku proposes", "llm_free_on_choose.jsonl", "remainder", False),
            ("sonnet proposes", "llm_free_sonnet_on_choose.jsonl", "remainder", False),
            ("haiku alone", "llm_free.jsonl", "random", False),
            ("sonnet alone", "llm_free_sonnet.jsonl", "random", False))
    for label, fname, sample, chooses in runs:
        rows = answers(fname)
        if not rows:
            continue
        filters = [("none", lambda a, it: True),
                   ("confidence ≥ 80", lambda a, it: (a.get("confidence") or 0) >= CONFIDENCE)]
        if not chooses:
            filters += [("in JADEN's candidates", lambda a, it: a["lg_code"] in it["candidates"]),
                        ("both (system 4b)", lambda a, it: a["lg_code"] in it["candidates"]
                         and (a.get("confidence") or 0) >= CONFIDENCE)]
        total_right = sum(1 for a in rows if a["lg_code"] and scorer.right(a["lg_code"], by_id[a["id"]]["truth"]))
        for fname_, f in filters:
            kept_right = kept_wrong = 0
            for a in rows:
                if not a["lg_code"]:
                    continue
                it = by_id[a["id"]]
                if not f(a, it):
                    continue
                ok = scorer.right(a["lg_code"], it["truth"])
                kept_right += ok
                kept_wrong += not ok
            kept = kept_right + kept_wrong
            lo, hi = wilson(kept_wrong, kept)
            res.setdefault("llm", {})[f"{label} | {fname_}"] = {"kept": kept, "wrong": kept_wrong,
                                                               "right_discarded": total_right - kept_right}
            lines.append(f"| {label} | {sample} | {fname_} | {kept:,} | {kept_wrong} ({100 * lo:.1f}–{100 * hi:.1f}%) | "
                         f"{total_right - kept_right:,} |")

    named = models["calibrated + name"]
    town1 = town(t1)
    base_right = base_wrong = remainder = 0
    for it in town1:
        if not it["candidates"]:
            continue
        p, j = top(named, it)
        if p >= named.tau:
            ok = scorer.right(it["candidates"][j], it["truth"])
            base_right += ok
            base_wrong += not ok
        else:
            remainder += 1
    lines += ["", "## 5. Projection: calibrated + name, then verified proposals (test 1, town only)", "",
              f"Town-only inputs: {len(town1):,}. Calibrated + name answers {base_right + base_wrong:,} "
              f"({base_right:,} right, {base_wrong:,} wrong). Inputs left with candidates (the population the "
              f"remainder sample was drawn from): {remainder:,}.", "",
              "| Proposals from | Kept per 1,000: right / wrong | Projected right | Projected wrong among answers |",
              "| :--- | :--- | ---: | ---: |"]
    for label in ("haiku proposes", "sonnet proposes"):
        key = f"{label} | both (system 4b)"
        if key not in res.get("llm", {}):
            continue
        kept = res["llm"][key]
        kr = kept["kept"] - kept["wrong"]
        kw = kept["wrong"]
        add_r, add_w = remainder * kr / 1000, remainder * kw / 1000
        right = base_right + add_r
        wrong = base_wrong + add_w
        res.setdefault("projection", {})[label] = {"remainder": remainder, "right_share": right / len(town1),
                                                   "wrong_among_answers": wrong / (right + wrong)}
        lines.append(f"| {label} | {kr} / {kw} | {100 * right / len(town1):.1f}% | {100 * wrong / (right + wrong):.2f}% |")

    # 6
    lines += ["", "## 6. Wilson intervals against a cluster bootstrap over identical inputs (town only)", "",
              "| Test | System | Answered | Wrong | Wilson 95% | Cluster bootstrap 95% |", "| :--- | :--- | ---: | ---: | :--- | :--- |"]
    for tname, items in (("test 1", town(t1)), ("test 2", town(t2))):
        rules = [(it["input"], not scorer.right(it["candidates"][0] if it["candidates"] else None, it["truth"]))
                 for it in items if it["status"] == "ACCEPTED"]
        cal = []
        for it in items:
            if it["candidates"]:
                p, j = top(models["calibrated"], it)
                if p >= models["calibrated"].tau:
                    cal.append((it["input"], not scorer.right(it["candidates"][j], it["truth"])))
        for sname, outcomes in (("rules", rules), ("calibrated", cal)):
            n, w = len(outcomes), sum(x for _, x in outcomes)
            lo, hi = wilson(w, n)
            clo, chi = cluster_ci(outcomes)
            res.setdefault("intervals", {})[f"{tname} {sname}"] = {"answered": n, "wrong": w, "wilson": [lo, hi],
                                                                    "cluster": [clo, chi]}
            lines.append(f"| {tname} | {sname} | {n:,} | {w:,} | {100 * lo:.3f}–{100 * hi:.3f}% | {100 * clo:.3f}–{100 * chi:.3f}% |")

    # 7
    del t1, t2
    train_n = len(load_items(ROOT / "benchmarks" / "calibration" / "data" / "train.pkl.gz"))
    calib_n = len(load_items(ROOT / "benchmarks" / "calibration" / "data" / "calib.pkl.gz"))
    dev_n = len(load_items(ROOT / "benchmarks" / "calibration" / "data" / "devcheck.pkl.gz"))
    res["sizes"] = {"train_inputs": train_n, "calib_inputs": calib_n, "devcheck_inputs": dev_n}
    lines += ["", "## 7. Sizes", "", f"- training inputs: {train_n:,}", f"- calibration inputs: {calib_n:,}",
              f"- development-check inputs: {dev_n:,}"]

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
