"""Re-measure the reverse lookup after the study (see results/POSTHOC.md).

Usage: python benchmarks/history/posthoc_reverse.py DIR   (DIR as used by evaluate_history.py)
"""

import json
import sys

import jaden
from jaden.history import former_municipality

folder = sys.argv[1]
inputs = {r["id"]: r for r in map(json.loads, open(f"{folder}/inputs.jsonl", encoding="utf-8"))}
n = agree = wrong = none = 0
for line in open(f"{folder}/reverse.jsonl", encoding="utf-8"):
    r = json.loads(line)
    n += 1
    f = former_municipality(jaden.normalize(inputs[r["id"]]["input"]))
    if f is None:
        none += 1
    elif f.code == r["expected"]:
        agree += 1
    else:
        wrong += 1
        print("wrong:", inputs[r["id"]]["input"], r["expected"], f.code, file=sys.stderr)
print(json.dumps({"eligible": n, "agree": agree, "wrong": wrong, "none": none}))
