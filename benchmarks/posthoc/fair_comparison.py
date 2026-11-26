"""Post-hoc: JADEN against jageocoder on equal terms (town-only input).

The pre-registered comparison scored jageocoder's first answer for every input, while JADEN may decline.
That mixes two differences: how well a tool ranks the candidates, and whether it is allowed to abstain.
This analysis separates them:

- jageocoder (first answer), as before;
- jageocoder that abstains: it answers only when every equally good match lies in one municipality
  (benchmarks/jabench/baselines/jageocoder_candidates_run.py), i.e. the simplest abstention rule its own
  output allows;
- JADEN's calibrated resolver at its threshold, and at the same share of answered inputs as each
  jageocoder variant (answering the inputs with the highest probabilities first): matched coverage.

jageocoder over all candidates is slow, so it runs on a random sample of 40,000 town-only inputs per test
(seed 2026), and all systems are scored on the same sample.

  sample   writes the samples:   fair_comparison.py sample --inputs T1/inputs.jsonl --out sample_t1.jsonl
  score    scores everything:    fair_comparison.py score --items T1/jaden_items.pkl.gz --sample sample_t1.jsonl
                                     --first T1/jageocoder.jsonl --candidates jgc_cand_t1.jsonl --name "test 1"
"""

import argparse
import gzip
import json
import pickle
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))

SEED = 2026
SIZE = 40000


def sample(inputs: Path, out: Path) -> None:
    rows = [line for line in open(inputs, encoding="utf-8") if json.loads(line)["variant"] == "town only"]
    random.Random(SEED).shuffle(rows)
    out.write_text("".join(rows[:SIZE]), encoding="utf-8")
    print(f"{min(SIZE, len(rows)):,} of {len(rows):,} town-only inputs")


def score(items_path: Path, sample_path: Path, first_path: Path, cand_path: Path, name: str, out: Path) -> None:
    from evaluate_heldout import Model, Scorer, wilson
    scorer = Scorer()
    ids = [json.loads(line)["id"] for line in open(sample_path, encoding="utf-8")]
    wanted = set(ids)
    with gzip.open(items_path, "rb") as fh:
        items = {it["id"]: it for it in pickle.load(fh)["items"] if it["id"] in wanted}
    first = {r["id"]: r.get("lg_code") for r in map(json.loads, open(first_path, encoding="utf-8")) if r["id"] in wanted}
    cands = {r["id"]: r["lg_codes"] for r in map(json.loads, open(cand_path, encoding="utf-8"))}
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    sel = [i for i in ids if i in items and items[i].get("known_truth", True) and i in cands]
    n = len(sel)
    rows: List[Tuple[str, int, int]] = []

    def add(label: str, answers: Dict[str, Optional[str]]) -> Tuple[int, int]:
        right = sum(1 for i in sel if answers.get(i) and scorer.right(answers[i], items[i]["truth"]))
        ans = sum(1 for i in sel if answers.get(i))
        rows.append((label, right, ans - right))
        return right, ans - right

    # jageocoder
    add("jageocoder, first answer", {i: first.get(i) for i in sel})
    abst = {i: (cands[i][0] if len(cands[i]) == 1 else None) for i in sel}
    add("jageocoder that abstains (one municipality among its best matches)", abst)
    # JADEN rules
    add("JADEN rules", {i: (items[i]["candidates"][0] if items[i]["status"] == "ACCEPTED" and items[i]["candidates"] else None)
                        for i in sel})
    # JADEN calibrated, at the threshold and at matched coverage
    for mname, key, use_name in (("JADEN calibrated", "address", False), ("JADEN calibrated + name", "address+name", True)):
        model = Model(spec["models"][key], use_name)
        scored = []
        for i in sel:
            it = items[i]
            if not it["candidates"]:
                continue
            p, _ = model.probs(it)
            j = max(range(len(p)), key=p.__getitem__)
            scored.append((p[j], i, it["candidates"][j]))
        add(f"{mname}, at its threshold", {i: c for p, i, c in scored if p >= model.tau})
        scored.sort(reverse=True)
        for target_label in ("jageocoder that abstains (one municipality among its best matches)", "jageocoder, first answer"):
            r = next(x for x in rows if x[0] == target_label)
            k = r[1] + r[2]
            short = "the abstaining jageocoder" if "abstains" in target_label else "jageocoder's first answer"
            add(f"{mname}, answering as many as {short}", {i: c for _p, i, c in scored[:k]})
    lines = [f"## {name}: town only, random sample of {n:,} inputs (seed {SEED})", "",
             "| System | Answered | Right | Wrong | Wrong among answers (95% CI) |", "| :--- | ---: | ---: | ---: | :--- |"]
    result = {"name": name, "n": n, "rows": []}
    for label, right, wrong in rows:
        ans = right + wrong
        lo, hi = wilson(wrong, ans)
        result["rows"].append({"system": label, "answered": ans, "right": right, "wrong": wrong})
        lines.append(f"| {label} | {100 * ans / n:.1f}% | {100 * right / n:.1f}% | {wrong:,} | "
                     f"{100 * wrong / max(1, ans):.2f}% ({100 * lo:.2f}–{100 * hi:.2f}%) |")
    out.mkdir(parents=True, exist_ok=True)
    tag = name.replace(" ", "")
    (out / f"fair_comparison_{tag}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"fair_comparison_{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["sample", "score"])
    ap.add_argument("--inputs", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--items", type=Path)
    ap.add_argument("--sample", type=Path)
    ap.add_argument("--first", type=Path)
    ap.add_argument("--candidates", type=Path)
    ap.add_argument("--name", default="test")
    args = ap.parse_args()
    if args.stage == "sample":
        sample(args.inputs, args.out)
    else:
        score(args.items, args.sample, args.first, args.candidates, args.name, args.out or HERE / "results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
