"""Post-hoc: the calibration step redone with a procedure whose guarantees hold, then applied to both tests.

The pre-registered procedure (benchmarks/calibration/train.py) had two weaknesses:

1. It scanned every threshold from low to high and kept the first whose 95% Clopper-Pearson bound met
   the 1% target. Testing many thresholds this way has no multiplicity control, so the 95% is not a 95%
   guarantee.
2. The temperature, the threshold and the conformal quantiles were all fitted on the same calibration
   half, while split-conformal coverage assumes the quantile is computed on data not used to fit the
   scores.

Here the model weights stay exactly as fitted (data/model.json); only the calibration step changes:

- the care-office calibration half is split again, by facility (name and municipality), into fold A
  and fold B;
- the temperature is fitted on fold A only;
- the threshold is chosen on fold B by fixed-sequence testing (Learn-then-Test, Angelopoulos et al.
  2021): thresholds are tested from the strictest to the loosest, each with the Clopper-Pearson bound
  required to hold for every input type, and the scan stops at the first failure. The scan starts at the
  strictest threshold at which every input type has 1,000 answers (decided from the scores alone). Because the sequence
  is fixed in advance and stops at the first failure, the chosen threshold controls the wrong-answer rate
  at the target with probability at least 95% (under exchangeability), with no correction needed;
- the conformal quantiles are computed on fold B with the fold-A temperature.

The result is applied to the development check half and to the stored items of both held-out tests.
This is an analysis after the tests: it is reported next to, not instead of, the pre-registered results.

Usage:
    python benchmarks/posthoc/recalibrate.py --test1 T1/jaden_items.pkl.gz --test2 T2/items_final.pkl.gz
"""

import argparse
import gzip
import hashlib
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "calibration"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))

import train  # noqa: E402
from candidates import FEATURES  # noqa: E402

GRID = 400
DELTA = 0.05
MIN_ANSWERS = 1000


def fold_of(item: Dict[str, Any]) -> str:
    key = f"{item['side']}|{item['truth']}"
    return "A" if int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % 2 == 0 else "B"


def fixed_sequence_threshold(per_variant: Dict[str, Tuple[np.ndarray, np.ndarray]], target: float) -> Tuple[float, int]:
    """Strictest to loosest; stop at the first threshold whose bound fails for any input type."""
    allp = np.concatenate([p for p, _ in per_variant.values()])
    grid = np.unique(np.quantile(allp, np.linspace(0, 1, GRID)))[::-1]
    # The sequence starts where every input type has MIN_ANSWERS answers. This uses the scores only, never
    # the labels, so the order is still fixed before any test is made; it avoids stopping at once on a
    # threshold so strict that no bound could pass.
    start = next((i for i, tau in enumerate(grid) if all(int((p >= tau).sum()) >= MIN_ANSWERS for p, _ in per_variant.values())), len(grid))
    chosen, tested = 1.0, 0
    for tau in grid[start:]:
        tested += 1
        ok = True
        for p, right in per_variant.values():
            sel = p >= tau
            k, n = int((~right[sel]).sum()), int(sel.sum())
            if n and train.clopper_upper(k, n, 1 - DELTA) > target:
                ok = False
                break
        if not ok:
            break
        chosen = float(tau)
    return chosen, tested


def spec_for(name: str, use_name: bool, calib: List[Dict[str, Any]], base: Dict[str, Any]) -> Dict[str, Any]:
    theta = np.array(base["w"] + base["v"])
    folds = np.array([fold_of(it) for it in calib])
    a = [it for it, f in zip(calib, folds) if f == "A"]
    b = [it for it, f in zip(calib, folds) if f == "B"]
    pa, pb = train.Packed(a, use_name), train.Packed(b, use_name)
    temperature = train.fit_temperature(theta, pa)
    best_p, right, _ = train.top_answers(pb, theta, temperature)
    vb = np.array([it["variant"] for it in b])
    per_variant = {v: (best_p[vb == v], right[vb == v]) for v in train.VARIANTS}
    tau, tested = fixed_sequence_threshold(per_variant, train.TARGET_RISK)
    qhat = {v: train.conformal_quantile(pb, theta, temperature, vb == v, train.ALPHA) for v in train.VARIANTS}
    return {"w": base["w"], "v": base["v"], "temperature": temperature, "threshold": tau, "conformal_qhat": qhat,
            "fold_sizes": [len(a), len(b)], "thresholds_tested": tested}


def evaluate(items: List[Dict[str, Any]], spec: Dict[str, Any], use_name: bool, variant_map: Dict[str, str]) -> Dict[str, Any]:
    from evaluate_heldout import Model, Scorer, ece, wilson
    model = Model(spec, use_name)
    scorer = Scorer()
    out: Dict[str, Any] = {}
    for v, qv in variant_map.items():
        sel = [it for it in items if it["variant"] == v and it.get("known_truth", True)]
        right = wrong = cov = size = 0
        pairs = []
        for it in sel:
            if not it["candidates"]:
                cov += 1
                size += 1
                continue
            p, p_none = model.probs(it)
            j = max(range(len(p)), key=p.__getitem__)
            ok = scorer.right(it["candidates"][j], it["truth"])
            pairs.append((p[j], ok))
            if p[j] >= model.tau:
                right += ok
                wrong += not ok
            q = spec["conformal_qhat"][qv]
            members = [i for i, pi in enumerate(p) if 1 - pi <= q]
            none_in = 1 - p_none <= q
            size += len(members) + int(none_in)
            t = it["label"] if 0 <= it["label"] < len(it["candidates"]) else None
            cov += (t in members) if t is not None else none_in
        n = len(sel)
        lo, hi = wilson(wrong, right + wrong)
        out[v] = {"n": n, "right": right, "wrong": wrong, "answered": right + wrong,
                  "wrong_rate": wrong / max(1, right + wrong), "wrong_ci": [lo, hi], "ece": ece(pairs),
                  "coverage": cov / max(1, n), "size": size / max(1, n)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test1", type=Path, required=True)
    ap.add_argument("--test2", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    base = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    calib = train.load("calib")

    def devcheck_items() -> List[Dict[str, Any]]:
        items = train.load("devcheck")
        for it in items:
            it.setdefault("known_truth", True)
            it["candidates"] = list(it["candidates"])
        return items

    def test_items(path: Path) -> List[Dict[str, Any]]:
        """Only the fields scoring needs, so that one test set at a time fits in memory."""
        with gzip.open(path, "rb") as fh:
            items = pickle.load(fh)["items"]
        keep = ("variant", "known_truth", "candidates", "x", "g", "label", "truth")
        return [{k: it[k] for k in keep if k in it} for it in items]
    result: Dict[str, Any] = {"features": FEATURES, "models": {}}
    lines = ["# Post-hoc: corrected calibration procedure", "",
             "Same model weights as the pre-registered resolver; temperature on one fold of the calibration half, "
             "threshold (fixed-sequence testing, 1% target, 95%) and conformal quantiles (95%) on the other. "
             "Applied after both tests; the pre-registered results stand as reported.", ""]
    for name, use_name in (("address", False), ("address+name", True)):
        old = base["models"][name]
        spec = spec_for(name, use_name, calib, old)
        result["models"][name] = {"spec": spec}
        lines += [f"## {name}", "",
                  f"Folds A / B: {spec['fold_sizes'][0]:,} / {spec['fold_sizes'][1]:,} inputs. "
                  f"Temperature {spec['temperature']:.3f} (pre-registered {old['temperature']:.3f}); threshold "
                  f"{spec['threshold']:.4f} (pre-registered {old['threshold']:.4f}), after testing "
                  f"{spec['thresholds_tested']} thresholds in order.", "",
                  "| Data | Input | Threshold | Right | Wrong among answers (95% CI) | ECE | Conformal coverage / size |",
                  "| :--- | :--- | :--- | ---: | :--- | ---: | :--- |"]
        sets = (("development check", devcheck_items, {v: v for v in train.VARIANTS}),
                ("test 1", lambda: test_items(args.test1), {v: v for v in train.VARIANTS}),
                ("test 2", lambda: test_items(args.test2), {"town only": "town only", "no prefecture": "with prefecture", "full": "full"}))
        for label, loader, vmap in sets:
            items = loader()
            for which, s in (("pre-registered", old), ("corrected", spec)):
                ev = evaluate(items, s, use_name, vmap)
                result["models"][name].setdefault(label, {})[which] = ev
                for v, c in ev.items():
                    lines.append(f"| {label} | {v} | {which} | {c['right'] / max(1, c['n']):.2%} | "
                                 f"{c['wrong_rate']:.2%} ({c['wrong_ci'][0]:.2%}–{c['wrong_ci'][1]:.2%}) | "
                                 f"{c['ece']:.4f} | {c['coverage']:.2%} / {c['size']:.2f} |")
            del items
        lines.append("")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "recalibration.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (args.out / "recalibration.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
