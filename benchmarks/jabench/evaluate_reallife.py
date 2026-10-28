"""Scores robustness on benchmarks/jabench/reallife.jsonl (see build_reallife.py).

An item passes when, compared with the clean address it was made from, the system returns
the same municipality and the same canonical address, and extracts exactly the building,
floor and room that were added (nothing else).

Usage:
    python benchmarks/jabench/evaluate_reallife.py [--gazetteer off]
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gazetteer", choices=["on", "off"], default="on")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    from jaden.engine import AddressNormalizer
    engine = AddressNormalizer(use_gazetteer=args.gazetteer == "on")
    items = [json.loads(line) for line in open(HERE / "reallife.jsonl", encoding="utf-8")]
    base_cache = {}
    passed, total = Counter(), Counter()
    failures = defaultdict(list)
    for it in items:
        base = base_cache.get(it["base"])
        if base is None:
            base = base_cache[it["base"]] = engine.normalize(it["base"])
        res = engine.normalize(it["input"])
        c = res.components
        b = base.components
        # Notes already in the published address ('病院内', '外') stay part of the building text
        expected_building = " ".join(x for x in (b.building, it["building"]) if x) or None
        checks = {
            "municipality": c.lg_code == b.lg_code == it["gold_lg"],
            "address": res.canonical.split(" ")[0] == base.canonical.split(" ")[0],
            "building": sorted((c.building or "").split()) == sorted((expected_building or "").split()),
            "floor": c.floor == (it["floor"] or b.floor),
            "unit": c.unit == (it["unit"] or b.unit),
        }
        total[it["variant"]] += 1
        if all(checks.values()):
            passed[it["variant"]] += 1
        else:
            failures[it["variant"]].append((it["input"], res.canonical,
                                            [k for k, ok in checks.items() if not ok],
                                            (c.building, c.floor, c.unit)))
    print("| Variant | Items | Pass |\n|---|---:|---:|")
    for v in total:
        print(f"| {v} | {total[v]} | {100 * passed[v] / total[v]:.1f}% |")
    print(f"| **all** | {sum(total.values())} | {100 * sum(passed.values()) / sum(total.values()):.1f}% |")
    for v, fails in failures.items():
        print(f"\n{v}: {len(fails)} failures")
        for f in fails[:args.examples]:
            print("  ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
