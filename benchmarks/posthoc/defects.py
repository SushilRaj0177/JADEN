"""Post-hoc: how many of the rules' wrong town-only answers in test 1 the two defects found there explain.

Test 1's error analysis found two rule defects; they were fixed after the test in commit db3c9aa. This
script takes the town-only inputs that the tested engine (01a23ba) answered wrongly and runs them through
both engines, each from its own git worktree, and counts how many the fixed engine no longer answers
wrongly. The test results themselves are not re-measured.

Usage:
    python benchmarks/posthoc/defects.py --test1 DIR1 --before WORKTREE_01a23ba --after WORKTREE_db3c9aa
"""

import argparse
import gzip
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))

RUNNER = """
import json, sys
import jaden
for line in sys.stdin:
    r = json.loads(line)
    v = jaden.validate(r["input"])
    print(json.dumps({"id": r["id"], "status": v.status, "lg_code": v.lg_code}))
"""


def run(root: Path, rows: list) -> dict:
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    out = subprocess.run([sys.executable, "-c", RUNNER], input="\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                         capture_output=True, text=True, env=env, cwd=root, check=True).stdout
    return {d["id"]: d for d in map(json.loads, out.splitlines())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test1", type=Path, required=True)
    ap.add_argument("--before", type=Path, required=True)
    ap.add_argument("--after", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    from evaluate_heldout import Scorer
    scorer = Scorer()
    with gzip.open(args.test1 / "jaden_items.pkl.gz", "rb") as fh:
        items = pickle.load(fh)["items"]
    wrong = [it for it in items if it["variant"] == "town only" and it["known_truth"] and it["status"] == "ACCEPTED"
             and not scorer.right(it["candidates"][0] if it["candidates"] else None, it["truth"])]
    rows = [{"id": it["id"], "input": it["input"], "truth": it["truth"]} for it in wrong]
    before, after = run(args.before, rows), run(args.after, rows)
    counts = {"tested_wrong": len(rows), "before_still_wrong": 0, "after_wrong": 0, "after_right": 0, "after_no_answer": 0}
    for r in rows:
        b, a = before[r["id"]], after[r["id"]]
        counts["before_still_wrong"] += b["status"] == "ACCEPTED" and not scorer.right(b["lg_code"], r["truth"])
        if a["status"] != "ACCEPTED":
            counts["after_no_answer"] += 1
        elif scorer.right(a["lg_code"], r["truth"]):
            counts["after_right"] += 1
        else:
            counts["after_wrong"] += 1
    fixed = counts["after_no_answer"] + counts["after_right"]
    lines = ["# Post-hoc: the two rule defects found in test 1", "",
             f"Town-only inputs the tested engine answered wrongly: {len(rows):,} "
             f"(re-run with that engine: {counts['before_still_wrong']:,} still wrong).", "",
             f"With the fix (db3c9aa): {fixed:,} are no longer wrong ({counts['after_no_answer']:,} now give no answer, "
             f"{counts['after_right']:,} are now right); {counts['after_wrong']:,} remain wrong.", ""]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "defects.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    (args.out / "defects.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
