"""The held-out test (PROTOCOL.md): every system on the MLIT welfare-facility addresses.

  prepare   JADEN's rules and the calibrated resolver on every test input
            -> DIR/jaden_items.pkl.gz
  samples   the pre-registered language-model samples (seed 2026)
            -> DIR/llm_choose_items.jsonl (1,000 town-only inputs the calibrated resolver with the
               name leaves unanswered, with candidates), DIR/llm_free_items.jsonl (1,000 random
               town-only inputs)
  report    everything scored -> benchmarks/heldout/results/

Usage:
    python benchmarks/heldout/evaluate_heldout.py prepare --dir DIR
    python benchmarks/heldout/evaluate_heldout.py samples --dir DIR
    (run benchmarks/heldout/llm.py, Geolonia and jageocoder on DIR's files)
    python benchmarks/heldout/evaluate_heldout.py report --dir DIR [--external geolonia=... jageocoder=...]
"""

import argparse
import gzip
import json
import math
import pickle
import random
import subprocess
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "calibration"))

VARIANTS = ("town only", "with prefecture", "full")
NO_OVERLAP = {"01", "03", "04", "05", "06"}   # categories that cannot be care offices
SEED = 2026
_B: Any = None


def _init() -> None:
    global _B
    from candidates import CandidateBuilder
    _B = CandidateBuilder()


def _work(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from candidates import label_of
    out = []
    for r in batch:
        item = _B.build(r["input"], r["side"])
        lg6 = next((lg for lg in _B.by_code if lg[:5] == r["truth"]), None)
        label = label_of(item, r["truth"], _B.by_code) if lg6 else -1
        out.append({"id": r["id"], "variant": r["variant"], "category": r["category"], "truth": r["truth"],
                    "status": item.status, "candidates": item.candidates, "x": item.x, "g": item.g, "label": label,
                    "known_truth": lg6 is not None, "input": r["input"], "side": r["side"]})
    return out


def prepare(folder: Path, jobs: int) -> None:
    rows = [json.loads(line) for line in open(folder / "inputs.jsonl", encoding="utf-8")]
    batches = [rows[i:i + 2000] for i in range(0, len(rows), 2000)]
    items: List[Dict[str, Any]] = []
    with Pool(jobs, initializer=_init) as pool:
        for i, part in enumerate(pool.imap(_work, batches), 1):
            items.extend(part)
            if i % 25 == 0:
                print(f"  {i * 2000:,} / {len(rows):,}", file=sys.stderr, flush=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    with gzip.open(folder / "jaden_items.pkl.gz", "wb") as fh:
        pickle.dump({"commit": commit, "items": items}, fh)
    print(f"{len(items):,} items at {commit}", file=sys.stderr)


class Model:
    def __init__(self, spec: Dict[str, Any], use_name: bool) -> None:
        self.w, self.v = spec["w"], spec["v"]
        self.t = spec["temperature"]
        self.tau = spec["threshold"]
        self.qhat = spec["conformal_qhat"]
        self.use_name = use_name

    def probs(self, item: Dict[str, Any]) -> Tuple[List[float], float]:
        from candidates import FEATURES
        name_cols = {FEATURES.index("name_mentions_muni"), FEATURES.index("name_mentions_pref")}
        scores = [sum(w * (0.0 if (j in name_cols and not self.use_name) else x) for j, (w, x) in enumerate(zip(self.w, row))) / self.t
                  for row in item["x"]]
        none = sum(v * g for v, g in zip(self.v, item["g"])) / self.t
        m = max(scores + [none])
        e = [math.exp(s - m) for s in scores]
        en = math.exp(none - m)
        z = sum(e) + en
        return [x / z for x in e], en / z


def samples(folder: Path) -> None:
    with gzip.open(folder / "jaden_items.pkl.gz", "rb") as fh:
        items = pickle.load(fh)["items"]
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    named = Model(spec["models"]["address+name"], True)
    town = [it for it in items if it["variant"] == "town only"]
    unanswered = []
    for it in town:
        if not it["candidates"]:
            continue
        p, _ = named.probs(it)
        if max(p) < named.tau:
            unanswered.append(it)
    rng = random.Random(SEED)
    choose = rng.sample(unanswered, min(1000, len(unanswered)))
    free = random.Random(SEED + 1).sample(town, min(1000, len(town)))
    for name, chosen in (("llm_choose_items.jsonl", choose), ("llm_free_items.jsonl", free)):
        with open(folder / name, "w", encoding="utf-8") as fh:
            for it in chosen:
                fh.write(json.dumps({"id": it["id"], "input": it["input"], "side": it["side"],
                                     "candidates": it["candidates"], "truth": it["truth"]}, ensure_ascii=False) + "\n")
    print(f"{len(unanswered):,} town-only inputs left unanswered with candidates; samples of {len(choose)} and {len(free)}")


# ----------------------------------------------------------------------------------------------- scoring

def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.2f}%" if n else "–"


def ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{100 * lo:.2f}–{100 * hi:.2f}%"


class Scorer:
    """Right when the answer is the row's municipality or a ward of the row's designated city."""

    def __init__(self) -> None:
        from jaden.data.loader import get_registry
        self.by_code = {m.lg_code: m for m in get_registry().list_municipalities()}
        self.by5 = {lg[:5]: m for lg, m in self.by_code.items()}

    def right(self, lg: Optional[str], truth5: str) -> bool:
        if not lg:
            return False
        if lg[:5] == truth5:
            return True
        t, m = self.by5.get(truth5), self.by5.get(lg[:5])
        return bool(t and m and t.entity_type == "designated_city" and m.ward and m.city == t.city
                    and m.prefecture_code == t.prefecture_code)


def ece(pairs: Sequence[Tuple[float, bool]], bins: int = 15) -> float:
    if not pairs:
        return float("nan")
    s = sorted(pairs)
    n = len(s)
    total = 0.0
    for b in range(bins):
        chunk = s[b * n // bins:(b + 1) * n // bins]
        if chunk:
            total += len(chunk) * abs(sum(p for p, _ in chunk) / len(chunk) - sum(r for _, r in chunk) / len(chunk))
    return total / n


def aurc(pairs: Sequence[Tuple[float, bool]], n_total: int) -> Tuple[float, List[Tuple[float, float]]]:
    s = sorted(pairs, key=lambda x: -x[0])
    wrong = 0
    risks = []
    curve = []
    for i, (_, ok) in enumerate(s, 1):
        wrong += not ok
        risks.append(wrong / i)
        if i % max(1, len(s) // 200) == 0 or i == len(s):
            curve.append((i / n_total, wrong / i))
    return (sum(risks) / len(risks) if risks else float("nan")), curve


def report(folder: Path, externals: List[str], out: Path) -> None:
    with gzip.open(folder / "jaden_items.pkl.gz", "rb") as fh:
        blob = pickle.load(fh)
    items, commit = blob["items"], blob["commit"]
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    models = {"JADEN calibrated": Model(spec["models"]["address"], False),
              "JADEN calibrated + name": Model(spec["models"]["address+name"], True)}
    scorer = Scorer()
    ext: Dict[str, Dict[str, Optional[str]]] = {}
    for e in externals:
        name, _, path = e.partition("=")
        ext[name] = {r["id"]: r.get("lg_code") for r in map(json.loads, open(path, encoding="utf-8"))}

    groups = {"all categories": lambda it: True, "categories that cannot be care offices": lambda it: it["category"] in NO_OVERLAP}
    table: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
    curves: Dict[str, Dict[str, List[Tuple[float, float]]]] = defaultdict(dict)
    reliability: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
    for gname, gfilter in groups.items():
        for v in VARIANTS:
            sel = [it for it in items if it["variant"] == v and it["known_truth"] and gfilter(it)]
            n = len(sel)
            # rules
            r_right = sum(1 for it in sel if it["status"] == "ACCEPTED" and scorer.right(it["candidates"][0] if it["candidates"] else None, it["truth"]))
            r_ans = sum(1 for it in sel if it["status"] == "ACCEPTED")
            table[gname][v]["JADEN rules"] = {"n": n, "right": r_right, "wrong": r_ans - r_right, "answered": r_ans}
            for mname, model in models.items():
                pairs = []
                right = wrong = 0
                conf_cov = conf_size = 0
                for it in sel:
                    if not it["candidates"]:
                        none_ok = True
                        conf_cov += none_ok
                        conf_size += 1
                        continue
                    p, p_none = model.probs(it)
                    j = max(range(len(p)), key=p.__getitem__)
                    ok = scorer.right(it["candidates"][j], it["truth"])
                    pairs.append((p[j], ok))
                    if p[j] >= model.tau:
                        right += ok
                        wrong += not ok
                    q = model.qhat[v]
                    members = [i for i, pi in enumerate(p) if 1 - pi <= q]
                    none_in = 1 - p_none <= q
                    conf_size += len(members) + int(none_in)
                    truth_idx = it["label"] if it["label"] < len(it["candidates"]) else None
                    conf_cov += (truth_idx in members) if truth_idx is not None else none_in
                area, curve = aurc(pairs, n)
                table[gname][v][mname] = {"n": n, "right": right, "wrong": wrong, "answered": right + wrong,
                                          "aurc": area, "ece": ece(pairs), "conformal_coverage": conf_cov / n if n else None,
                                          "conformal_size": conf_size / n if n else None}
                if gname == "all categories":
                    curves[v][mname] = curve
                    if v == "town only":
                        reliability[mname] = pairs
            for ename, answers in ext.items():
                right = sum(1 for it in sel if scorer.right(answers.get(it["id"]), it["truth"]))
                ans = sum(1 for it in sel if answers.get(it["id"]))
                table[gname][v][ename] = {"n": n, "right": right, "wrong": ans - right, "answered": ans}
                if gname == "all categories":
                    curves[v][ename] = [(ans / n, (ans - right) / ans if ans else 0.0)]
            rules = table[gname][v]["JADEN rules"]
            if gname == "all categories":
                curves[v]["JADEN rules"] = [(rules["answered"] / n, rules["wrong"] / max(1, rules["answered"]))]

    llm = llm_results(folder, items, scorer)
    write_report(out, commit, table, llm, spec)
    plot(out, curves, reliability)


def llm_results(folder: Path, items: List[Dict[str, Any]], scorer: Scorer) -> Dict[str, Any]:
    by_id = {it["id"]: it for it in items}
    res: Dict[str, Any] = {}
    for mode, items_file in (("choose", "llm_choose_items.jsonl"), ("free", "llm_free_items.jsonl"),
                             ("free on the choose sample", "llm_choose_items.jsonl")):
        out_file = folder / {"choose": "llm_choose.jsonl", "free": "llm_free.jsonl",
                             "free on the choose sample": "llm_free_on_choose.jsonl"}[mode]
        if not out_file.exists():
            continue
        answers = [json.loads(line) for line in open(out_file, encoding="utf-8")]
        n = len(answers)
        right = wrong = invented = verified_right = verified_wrong = 0
        for a in answers:
            it = by_id[a["id"]]
            if a["invented"]:
                invented += 1
            if a["lg_code"]:
                ok = scorer.right(a["lg_code"], it["truth"])
                right += ok
                wrong += not ok
                if mode != "choose" and a["lg_code"] in it["candidates"]:
                    verified_right += ok
                    verified_wrong += not ok
        res[mode] = {"n": n, "right": right, "wrong": wrong, "invented": invented,
                     "verified_right": verified_right, "verified_wrong": verified_wrong}
    return res


def write_report(out: Path, commit: str, table: Dict[str, Any], llm: Dict[str, Any], spec: Dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Held-out test: MLIT welfare facilities (2023)", "",
             f"Run once at commit `{commit[:10]}` under `benchmarks/heldout/PROTOCOL.md`. Right / wrong are counts of "
             "answers naming the row's municipality or another one; percentages are of all inputs; the interval is the "
             "Wilson 95% interval of the wrong-answer rate among answers.", ""]
    for gname, per_v in table.items():
        lines += [f"## {gname[0].upper() + gname[1:]}", "",
                  "| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | AURC | ECE | Conformal 95%: coverage / size |",
                  "| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | ---: | :--- |"]
        for v, systems in per_v.items():
            label = v
            for sname, s in systems.items():
                n, r, w, a = s["n"], s["right"], s["wrong"], s["answered"]
                extra = (f"{s['aurc']:.4f} | {s['ece']:.4f} | {100 * s['conformal_coverage']:.2f}% / {s['conformal_size']:.2f}"
                         if "aurc" in s else "– | – | –")
                lines.append(f"| {label} | {sname} | {n:,} | {pct(r, n)} | {w:,} | {pct(w, a)} ({ci(w, a)}) | "
                             f"{pct(n - a, n)} | {extra} |")
                label = ""
        lines.append("")
    if llm:
        lines += ["## Language model (claude-haiku-5-5)", "",
                  "| Run | Inputs | Answered | Right | Wrong (95% CI among answers) | Named no existing municipality | Kept by JADEN's candidates: right / wrong |",
                  "| :--- | ---: | ---: | ---: | :--- | ---: | :--- |"]
        for mode, s in llm.items():
            a = s["right"] + s["wrong"]
            kept = (f"{s['verified_right']:,} / {s['verified_wrong']:,}" if mode != "choose" else "– (only candidates can be chosen)")
            lines.append(f"| {mode} | {s['n']:,} | {a:,} | {s['right']:,} | {s['wrong']:,} ({ci(s['wrong'], a)}) | "
                         f"{s['invented']:,} | {kept} |")
        lines.append("")
    (out / "heldout_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "heldout_scores.json").write_text(json.dumps({"commit": commit, "table": table, "llm": llm,
                                                          "thresholds": {k: m["threshold"] for k, m in spec["models"].items()}},
                                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines))


def plot(out: Path, curves: Dict[str, Dict[str, List[Tuple[float, float]]]],
         reliability: Dict[str, List[Tuple[float, bool]]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, v in zip(axes, VARIANTS):
        for name, pts in curves[v].items():
            xs, ys = zip(*pts)
            if len(pts) == 1:
                ax.scatter(xs, [100 * y for y in ys], label=name, s=40, zorder=3)
            else:
                ax.plot(xs, [100 * y for y in ys], label=name)
        ax.set_title(v)
        ax.set_xlabel("share of inputs answered")
        ax.set_xlim(0, 1)
        ax.set_yscale("symlog", linthresh=0.1)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("wrong answers among answers (%)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "risk_coverage.png", dpi=150)
    fig, ax = plt.subplots(figsize=(5, 5))
    for name, pairs in reliability.items():
        s = sorted(pairs)
        n = len(s)
        xs, ys = [], []
        for b in range(15):
            chunk = s[b * n // 15:(b + 1) * n // 15]
            if chunk:
                xs.append(sum(p for p, _ in chunk) / len(chunk))
                ys.append(sum(r for _, r in chunk) / len(chunk))
        ax.plot(xs, ys, marker="o", label=name)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("predicted probability (town only)")
    ax.set_ylabel("observed share right")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "reliability.png", dpi=150)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["prepare", "samples", "report"])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--external", nargs="*", default=[])
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare(args.dir, args.jobs)
    elif args.stage == "samples":
        samples(args.dir)
    else:
        report(args.dir, args.external, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
