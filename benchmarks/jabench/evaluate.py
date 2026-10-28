"""JA-AddrBench evaluation.

Scores address resolvers on benchmarks/jabench/jabench.jsonl.

For every item a system either ANSWERS (commits to one municipality) or ABSTAINS
(reports ambiguity, rejects the input, or cannot resolve it). From that:

  accuracy        correct answers / items                      (valid items)
  coverage        answers / items                              (valid items)
  precision       correct answers / answers                    (valid items)
  wrong-answer    wrong answers / items: committed to the wrong municipality
  false-accept    answers / items                              (invalid items: should be 0)
  geo error       distance from the system's point to the surveyed school point

Built-in systems:
  jaden               the current engine (gazetteer on)
  jaden-parser-only   the same engine with the gazetteer off (v0.1 behaviour)
  jaden+blocks        jaden with MLIT block-level data (--blocks-dir, from `jaden data fetch-blocks`)

External systems are scored from a JSONL file of {"id", "lg_code" | null, "lat", "lon"}
(see baselines/README.md):  --external geolonia=path.jsonl

Usage:
    python benchmarks/jabench/evaluate.py [--systems jaden jaden-parser-only] [--external NAME=PATH]
"""

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

VALID_VARIANTS = ("original", "no_pref", "town_only", "noisy", "romaji", "former_name")
INVALID_VARIANTS = ("wrong_pref", "chome_99", "non_address")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def jaden_system(use_gazetteer: bool, blocks_dir: Optional[Path] = None) -> Callable[[str], Dict[str, Any]]:
    from jaden.engine import AddressNormalizer
    from jaden.data.gazetteer import Gazetteer
    gaz = Gazetteer()
    # Block-level data is optional per machine; only the jaden+blocks system may see it
    gaz.block_dirs = (lambda: [blocks_dir]) if blocks_dir else (lambda: [])  # type: ignore[method-assign]
    engine = AddressNormalizer(gazetteer=gaz, use_gazetteer=use_gazetteer)

    def run(text: str) -> Dict[str, Any]:
        v = engine.validate(text)
        n = engine.normalize(text)
        answered = v.status == "ACCEPTED" and v.lg_code is not None
        candidates = [c.rsplit("(", 1)[1].rstrip(")") for c in v.ambiguous_candidates]
        return {"lg_code": v.lg_code if answered else None, "status": v.status,
                "lat": n.latitude if answered else None, "lon": n.longitude if answered else None,
                "level": n.location_level if answered else None, "candidates": candidates}
    return run


def load_external(path: Path) -> Dict[str, Dict[str, Any]]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out[r["id"]] = r
    return out


def score(items: List[Dict[str, Any]], results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    table: Dict[str, Any] = {}
    for variant in VALID_VARIANTS + INVALID_VARIANTS:
        subset = [it for it in items if it["variant"] == variant]
        if not subset:
            continue
        n = len(subset)
        answered = [it for it in subset if results[it["id"]].get("lg_code")]
        if variant in VALID_VARIANTS:
            correct = [it for it in answered if results[it["id"]]["lg_code"] in it.get("gold_any", [it["gold_lg"]])]
            dists = [haversine_km(results[it["id"]]["lat"], results[it["id"]]["lon"], it["lat"], it["lon"])
                     for it in correct if results[it["id"]].get("lat") is not None]
            abstained = [it for it in subset if not results[it["id"]].get("lg_code")]
            with_cands = [it for it in abstained if results[it["id"]].get("candidates")]
            table[variant] = {
                "n": n,
                "wrong_answers": len(answered) - len(correct),
                "abstained": len(abstained),
                "abstained_with_candidates": len(with_cands),
                "candidate_recall": (sum(any(g in results[it["id"]]["candidates"] for g in it.get("gold_any", [it["gold_lg"]]))
                                         for it in with_cands)
                                     / len(with_cands)) if with_cands else None,
                "mean_candidates": (statistics.mean(len(results[it["id"]]["candidates"]) for it in with_cands)
                                    if with_cands else None),
                "median_candidates": (statistics.median(len(results[it["id"]]["candidates"]) for it in with_cands)
                                      if with_cands else None),
                "accuracy": len(correct) / n,
                "coverage": len(answered) / n,
                "precision": len(correct) / len(answered) if answered else None,
                "wrong_answer_rate": (len(answered) - len(correct)) / n,
                "geo_n": len(dists),
                "geo_median_km": statistics.median(dists) if dists else None,
                "geo_p90_km": sorted(dists)[int(0.9 * (len(dists) - 1))] if dists else None,
                "geo_within_1km": sum(d <= 1 for d in dists) / len(dists) if dists else None,
            }
        else:
            table[variant] = {"n": n, "false_accepts": len(answered), "false_accept_rate": len(answered) / n}
    return table


def fmt(x: Optional[float], pct: bool = True) -> str:
    if x is None:
        return "–"
    return f"{100 * x:.1f}%" if pct else f"{x:.2f}"


def report(all_scores: Dict[str, Dict[str, Any]], timings: Dict[str, float]) -> str:
    lines = ["## Valid addresses (higher accuracy/precision, lower wrong-answer is better)", "",
             "| System | Variant | Accuracy | Coverage | Precision | Wrong answers | Geo median | Geo ≤1 km |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, sc in all_scores.items():
        for v in VALID_VARIANTS:
            if v in sc:
                s = sc[v]
                geo = f"{s['geo_median_km'] * 1000:.0f} m" if s["geo_median_km"] is not None else "–"
                lines.append(f"| {name} | {v} | {fmt(s['accuracy'])} | {fmt(s['coverage'])} | {fmt(s['precision'])} | "
                             f"{fmt(s['wrong_answer_rate'])} | {geo} | {fmt(s['geo_within_1km'])} |")
    lines += ["", "## Invalid inputs (false-accept rate: lower is better)", "",
              "| System | " + " | ".join(INVALID_VARIANTS) + " |", "|---|" + "---:|" * len(INVALID_VARIANTS)]
    for name, sc in all_scores.items():
        lines.append(f"| {name} | " + " | ".join(fmt(sc[v]["false_accept_rate"]) if v in sc else "–"
                                               for v in INVALID_VARIANTS) + " |")
    lines += ["", "## When a system abstains with a candidate list", "",
              "| System | Variant | Abstained | With candidates | Gold in list | Median list size |",
              "|---|---|---:|---:|---:|---:|"]
    for name, sc in all_scores.items():
        for v in VALID_VARIANTS:
            s = sc.get(v)
            if s and s.get("abstained_with_candidates"):
                lines.append(f"| {name} | {v} | {s['abstained']} | {s['abstained_with_candidates']} | "
                             f"{fmt(s['candidate_recall'])} | {s['median_candidates']:.0f} |")
    if timings:
        lines += ["", "## Throughput", "", "| System | Items/s |", "|---|---:|"]
        lines += [f"| {k} | {v:,.0f} |" for k, v in timings.items()]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Score address resolvers on JA-AddrBench.")
    ap.add_argument("--bench", type=Path, default=HERE / "jabench.jsonl")
    ap.add_argument("--systems", nargs="*", default=["jaden", "jaden-parser-only"])
    ap.add_argument("--external", nargs="*", default=[], metavar="NAME=PATH")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--blocks-dir", type=Path, help="directory of blocks/NN.tsv.gz for the jaden+blocks system")
    args = ap.parse_args(argv)

    with open(args.bench, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    builtin = {"jaden": lambda: jaden_system(True), "jaden-parser-only": lambda: jaden_system(False),
               "jaden+blocks": lambda: jaden_system(True, args.blocks_dir)}
    all_scores: Dict[str, Dict[str, Any]] = {}
    timings: Dict[str, float] = {}
    args.out.mkdir(parents=True, exist_ok=True)

    for name in args.systems:
        run = builtin[name]()
        run(items[0]["input"])  # load data before timing
        t0 = time.perf_counter()
        results = {it["id"]: run(it["input"]) for it in items}
        timings[name] = len(items) / (time.perf_counter() - t0)
        with open(args.out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps({"id": it["id"], **results[it["id"]]}, ensure_ascii=False) + "\n")
        all_scores[name] = score(items, results)

    for spec in args.external:
        name, _, path = spec.partition("=")
        ext = load_external(Path(path))
        missing = [it["id"] for it in items if it["id"] not in ext]
        if missing:
            print(f"warning: {name} has no result for {len(missing)} items; counted as abstentions", file=sys.stderr)
        results = {it["id"]: ext.get(it["id"], {"lg_code": None}) for it in items}
        all_scores[name] = score(items, results)

    with open(args.out / "scores.json", "w", encoding="utf-8") as f:
        json.dump({"scores": all_scores, "items_per_second": timings}, f, ensure_ascii=False, indent=2)
    text = report(all_scores, timings)
    (args.out / "report.md").write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
