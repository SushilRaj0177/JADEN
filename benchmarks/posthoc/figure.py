"""Post-hoc figure: wrong-answer rate against the share of inputs answered, town-only input, both tests.

JADEN's calibrated resolver as curves (answering the most probable inputs first), and single points for
JADEN's rules, the calibrated resolver at its threshold, jageocoder's first answer and jageocoder that
abstains. Same random samples as fair_comparison.py.

Usage:
    python benchmarks/posthoc/figure.py --t1 T1/jaden_items.pkl.gz sample_t1.jsonl T1/jageocoder.jsonl jgc_cand_t1.jsonl \
                                        --t2 T2/items_final.pkl.gz sample_t2.jsonl T2/jageocoder.jsonl jgc_cand_t2.jsonl \
                                        --out paper/arxiv/fair_curves.pdf
"""

import argparse
import gzip
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))


def panel(ax: Any, files: List[str], title: str) -> None:
    from evaluate_heldout import Model, Scorer
    items_path, sample_path, first_path, cand_path = map(Path, files)
    scorer = Scorer()
    ids = [json.loads(line)["id"] for line in open(sample_path, encoding="utf-8")]
    wanted = set(ids)
    with gzip.open(items_path, "rb") as fh:
        items = {it["id"]: it for it in pickle.load(fh)["items"] if it["id"] in wanted}
    first = {r["id"]: r.get("lg_code") for r in map(json.loads, open(first_path, encoding="utf-8")) if r["id"] in wanted}
    cands = {r["id"]: r["lg_codes"] for r in map(json.loads, open(cand_path, encoding="utf-8"))}
    sel = [i for i in ids if i in items and items[i].get("known_truth", True) and i in cands]
    n = len(sel)
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    colors = {"address": "#1f4e79", "address+name": "#6baed6"}
    for key, use_name, label in (("address", False, "JADEN calibrated"), ("address+name", True, "JADEN calibrated + name")):
        model = Model(spec["models"][key], use_name)
        scored = []
        for i in sel:
            it = items[i]
            if it["candidates"]:
                p, _ = model.probs(it)
                j = max(range(len(p)), key=p.__getitem__)
                scored.append((p[j], scorer.right(it["candidates"][j], it["truth"])))
        scored.sort(key=lambda x: -x[0])
        xs, ys, wrong = [], [], 0
        for k, (_p, ok) in enumerate(scored, 1):
            wrong += not ok
            if k % 50 == 0 or k == len(scored):
                xs.append(100 * k / n)
                ys.append(100 * wrong / k)
        ax.plot(xs, ys, color=colors[key], lw=1.8, label=label)
        at = [ok for p, ok in scored if p >= model.tau]
        ax.plot(100 * len(at) / n, 100 * (len(at) - sum(at)) / max(1, len(at)), "o", color=colors[key], ms=6,
                mec="white", zorder=5)

    def point(answers: Dict[str, Any], marker: str, color: str, label: str) -> None:
        ans = [i for i in sel if answers.get(i)]
        right = sum(1 for i in ans if scorer.right(answers[i], items[i]["truth"]))
        ax.plot(100 * len(ans) / n, 100 * (len(ans) - right) / max(1, len(ans)), marker, color=color, ms=8,
                mec="black", mew=0.6, label=label, zorder=6)

    point({i: (items[i]["candidates"][0] if items[i]["status"] == "ACCEPTED" and items[i]["candidates"] else None)
           for i in sel}, "s", "#2ca02c", "JADEN rules")
    point({i: first.get(i) for i in sel}, "^", "#d62728", "jageocoder, first answer")
    point({i: (cands[i][0] if len(cands[i]) == 1 else None) for i in sel}, "D", "#ff7f0e", "jageocoder that abstains")
    ax.set_title(f"{title} (town only, {n:,} inputs)", fontsize=10)
    ax.set_xlabel("inputs answered (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 25)
    ax.grid(alpha=0.3)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t1", nargs=4, required=True)
    ap.add_argument("--t2", nargs=4, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    panel(axes[0], args.t1, "Test 1: welfare facilities")
    panel(axes[1], args.t2, "Test 2: medical facilities")
    axes[0].set_ylabel("wrong among answers (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
