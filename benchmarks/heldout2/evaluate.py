"""Held-out test 2 (PROTOCOL.md): every system on the MHLW medical facility addresses.

  prepare   JADEN's rules and the resolver's candidates on every input, with the engine found under
            --root (this checkout, or a worktree of the commit before the audits)
            -> DIR/items_<tag>.pkl.gz  (with --geo also JADEN's offline point for full addresses)
  external  DIR/external_inputs.jsonl ({"id", "input"}) for the Geolonia and jageocoder runners
  report    everything scored -> benchmarks/heldout2/results/

Usage:
    python benchmarks/heldout2/evaluate.py prepare --dir DIR --tag final --geo
    python benchmarks/heldout2/evaluate.py prepare --dir DIR --tag before --root WORKTREE_AT_01a23ba
    python benchmarks/heldout2/evaluate.py external --dir DIR
    python benchmarks/heldout2/evaluate.py report --dir DIR --external geolonia=... jageocoder=...
"""

import argparse
import gzip
import json
import pickle
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
VARIANTS = ("full", "no prefecture", "town only")
GROUPS = ("all rows", "unseen rows")
_B: Any = None
_GEO = False


def _init(root: str, geo: bool) -> None:
    global _B, _GEO
    sys.path.insert(0, str(Path(root) / "src"))
    sys.path.insert(0, str(Path(root) / "benchmarks" / "calibration"))
    from candidates import CandidateBuilder
    _B, _GEO = CandidateBuilder(), geo


def _work(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from candidates import label_of
    out = []
    for r in batch:
        item = _B.build(r["input"], r["side"])
        lg6 = next((lg for lg in _B.by_code if lg[:5] == r["truth"]), None)
        rec = {"id": r["id"], "variant": r["variant"], "category": r["category"], "truth": r["truth"],
               "unseen": r["unseen"], "status": item.status, "candidates": item.candidates, "x": item.x, "g": item.g,
               "label": label_of(item, r["truth"], _B.by_code) if lg6 else -1, "known_truth": lg6 is not None,
               "input": r["input"]}
        if _GEO and r["variant"] == "full":
            import jaden
            res = jaden.normalize(r["input"])
            rec["point"] = (res.latitude, res.longitude, getattr(res, "location_level", None))
            rec["published"] = (r["lat"], r["lon"])
        out.append(rec)
    return out


def prepare(folder: Path, root: Path, tag: str, geo: bool, jobs: int) -> None:
    rows = [json.loads(line) for line in open(folder / "inputs.jsonl", encoding="utf-8")]
    batches = [rows[i:i + 2000] for i in range(0, len(rows), 2000)]
    items: List[Dict[str, Any]] = []
    with Pool(jobs, initializer=_init, initargs=(str(root), geo)) as pool:
        for i, part in enumerate(pool.imap(_work, batches), 1):
            items.extend(part)
            if i % 25 == 0:
                print(f"  {i * 2000:,} / {len(rows):,}", file=sys.stderr, flush=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=root).stdout.strip()
    with gzip.open(folder / f"items_{tag}.pkl.gz", "wb") as fh:
        pickle.dump({"commit": commit, "items": items}, fh)
    print(f"{len(items):,} items at {commit}", file=sys.stderr)


def external(folder: Path) -> None:
    n = 0
    with open(folder / "external_inputs.jsonl", "w", encoding="utf-8") as fh:
        for line in open(folder / "inputs.jsonl", encoding="utf-8"):
            r = json.loads(line)
            fh.write(json.dumps({"id": r["id"], "input": r["input"]}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n:,} inputs")


# ----------------------------------------------------------------------------------------------- scoring

def _load(folder: Path, tag: str) -> Tuple[str, List[Dict[str, Any]]]:
    with gzip.open(folder / f"items_{tag}.pkl.gz", "rb") as fh:
        blob = pickle.load(fh)
    return blob["commit"], blob["items"]


def report(folder: Path, externals: List[str], out: Path) -> None:
    sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))
    from evaluate_heldout import Model, Scorer, ece, wilson
    sys.path.insert(0, str(ROOT / "benchmarks" / "realdata"))
    from common import haversine_km

    commit, items = _load(folder, "final")
    commit_before, before = _load(folder, "before")
    before_by_id = {it["id"]: it for it in before}
    spec = json.loads((ROOT / "benchmarks" / "calibration" / "data" / "model.json").read_text(encoding="utf-8"))
    models = {"JADEN calibrated": Model(spec["models"]["address"], False),
              "JADEN calibrated + name": Model(spec["models"]["address+name"], True)}
    qvar = {"full": "full", "no prefecture": "with prefecture", "town only": "town only"}
    scorer = Scorer()
    ext: Dict[str, Dict[str, Optional[str]]] = {}
    for e in externals:
        name, _, path = e.partition("=")
        ext[name] = {r["id"]: r.get("lg_code") for r in map(json.loads, open(path, encoding="utf-8"))}

    def rules(it: Optional[Dict[str, Any]]) -> Tuple[bool, bool]:
        """(answered, right) for JADEN's rules."""
        if it is None or it["status"] != "ACCEPTED":
            return False, False
        return True, scorer.right(it["candidates"][0] if it["candidates"] else None, it["truth"])

    table: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = defaultdict(lambda: defaultdict(dict))
    examples: Dict[str, List[str]] = defaultdict(list)
    audit_flips: Dict[str, Counter] = defaultdict(Counter)
    for g in GROUPS:
        for v in VARIANTS:
            sel = [it for it in items if it["variant"] == v and it["known_truth"] and (g == "all rows" or it["unseen"])]
            n = len(sel)
            for label, source in (("JADEN rules (final)", None), ("JADEN rules (before the audits)", before_by_id)):
                ans = right = 0
                for it in sel:
                    a, ok = rules(it if source is None else source.get(it["id"]))
                    ans += a
                    right += ok
                    if source is None and a and not ok and g == "all rows" and len(examples[v]) < 15:
                        examples[v].append(f"`{it['input']}` → {it['candidates'][0]} (row: {it['truth']})")
                    if source is not None and g == "all rows":
                        a0, ok0 = rules(it)
                        if ok0 != ok or a0 != a:
                            audit_flips[v][f"before {'right' if ok else 'wrong' if a else 'no answer'} → final "
                                           f"{'right' if ok0 else 'wrong' if a0 else 'no answer'}"] += 1
                table[g][v][label] = {"n": n, "right": right, "wrong": ans - right, "answered": ans}
            for mname, model in models.items():
                pairs: List[Tuple[float, bool]] = []
                right = wrong = cov = size = 0
                q = model.qhat[qvar[v]]
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
                    members = [i for i, pi in enumerate(p) if 1 - pi <= q]
                    none_in = 1 - p_none <= q
                    size += len(members) + int(none_in)
                    t = it["label"] if 0 <= it["label"] < len(it["candidates"]) else None
                    cov += (t in members) if t is not None else none_in
                table[g][v][mname] = {"n": n, "right": right, "wrong": wrong, "answered": right + wrong,
                                      "ece": ece(pairs), "coverage": cov / n if n else None,
                                      "size": size / n if n else None}
            for ename, answers in ext.items():
                ans = sum(1 for it in sel if answers.get(it["id"]))
                right = sum(1 for it in sel if scorer.right(answers.get(it["id"]), it["truth"]))
                table[g][v][ename] = {"n": n, "right": right, "wrong": ans - right, "answered": ans}

    # offline points against the publisher's coordinates (descriptive)
    dist: Dict[str, List[float]] = defaultdict(list)
    for it in items:
        if "point" not in it:
            continue
        lat, lon, level = it["point"]
        try:
            plat, plon = float(it["published"][0]), float(it["published"][1])
        except (TypeError, ValueError):
            continue
        if lat is None or not (20 < plat < 50 and 120 < plon < 155):
            continue
        dist[level or "?"].append(haversine_km(lat, lon, plat, plon))

    def wrong_hi(cell: Dict[str, Any]) -> float:
        return wilson(cell["wrong"], cell["answered"])[1] if cell["answered"] else 0.0

    full, nop, town = (table["all rows"][v] for v in VARIANTS)
    final, bef = "JADEN rules (final)", "JADEN rules (before the audits)"
    others = [e for e in ext]
    hyp = {
        "H1": full[final]["answered"] >= 0.995 * full[final]["n"] and wrong_hi(full[final]) <= 0.0005,
        "H2": wrong_hi(nop[final]) <= 0.001 and all(nop[final]["wrong"] < nop[e]["wrong"] for e in others) and bool(others),
        "H3": wrong_hi(town[final]) <= 0.005 and all(town[final]["wrong"] < town[e]["wrong"] for e in others) and bool(others),
        "H4": wilson(town["JADEN calibrated"]["wrong"], town["JADEN calibrated"]["answered"])[0] <= 0.01,
        "H5": (town["JADEN calibrated"]["coverage"] or 0) >= 0.95,
        "H6": all(table[g][v][final]["wrong"] <= table[g][v][bef]["wrong"]
                  and table[g][v][final]["right"] >= table[g][v][bef]["right"]
                  for g in GROUPS for v in ("full", "no prefecture")),
    }
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps({"commit": commit, "commit_before": commit_before, "table": table,
                                                 "hypotheses": hyp, "inputs": summary,
                                                 "audit_flips": {k: dict(c) for k, c in audit_flips.items()},
                                                 "distance_km_median": {k: statistics.median(d) for k, d in dist.items()}},
                                                ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_report(out, commit, commit_before, table, hyp, summary, examples, audit_flips, dist, wilson)


def write_report(out: Path, commit: str, commit_before: str, table: Any, hyp: Dict[str, bool], summary: Dict[str, int],
                 examples: Dict[str, List[str]], flips: Dict[str, Counter], dist: Dict[str, List[float]], wilson: Any) -> None:
    def pct(k: int, n: int) -> str:
        return f"{100 * k / n:.2f}%" if n else "–"

    def ci(k: int, n: int) -> str:
        lo, hi = wilson(k, n)
        return f"{100 * k / n:.3f}% ({100 * lo:.3f}–{100 * hi:.3f}%)" if n else "–"

    lines = ["# Held-out test 2: MHLW medical facilities (2026-06-01)", "",
             f"Run once at commit `{commit[:10]}` under `benchmarks/heldout2/PROTOCOL.md`; \"before the audits\" is the "
             f"engine at `{commit_before[:10]}`. Right and wrong count answers that name the row's municipality or "
             "another one; percentages are of all inputs; the interval is the Wilson 95% interval of the wrong-answer "
             "rate among answers.", "", "## Inputs", ""]
    lines += [f"- {k}: {v:,}" for k, v in summary.items()]
    lines += ["", "## Hypotheses", ""]
    lines += [f"- **{k}**: {'holds' if ok else 'does not hold'}" for k, ok in hyp.items()]
    for g in GROUPS:
        lines += ["", f"## {g.capitalize()}", "",
                  "| Input | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer | ECE | Conformal 95%: coverage / size |",
                  "| :--- | :--- | ---: | ---: | ---: | :--- | ---: | ---: | :--- |"]
        for v in VARIANTS:
            for i, (s, c) in enumerate(table[g][v].items()):
                extra = (f"{c['ece']:.4f} | {100 * c['coverage']:.2f}% / {c['size']:.2f}" if "ece" in c and c["n"] else "– | –")
                lines.append(f"| {v if i == 0 else ''} | {s} | {c['n']:,} | {pct(c['right'], c['n'])} | {c['wrong']:,} | "
                             f"{ci(c['wrong'], c['answered'])} | {pct(c['n'] - c['answered'], c['n'])} | {extra} |")
    lines += ["", "## Before and after the audits (all rows)", "",
              "Inputs whose outcome under JADEN's rules changed between the two engines.", ""]
    for v in VARIANTS:
        lines.append(f"- {v}: " + (", ".join(f"{k}: {n:,}" for k, n in sorted(flips[v].items())) or "no change"))
    lines += ["", "## JADEN rules (final): wrong answers (first 15 per input)", ""]
    for v in VARIANTS:
        lines += [f"**{v}**", ""] + [f"- {e}" for e in examples[v]] + [""]
    lines += ["## JADEN's offline point against the publisher's coordinates (full addresses, descriptive)", "",
              "The publisher's coordinates are its own geocoding, so this is agreement between two systems.", "",
              "| JADEN point level | Addresses | Median distance | Within 1 km |", "| :--- | ---: | ---: | ---: |"]
    for level, d in sorted(dist.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {level} | {len(d):,} | {1000 * statistics.median(d):.0f} m | {pct(sum(x <= 1 for x in d), len(d))} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["prepare", "external", "report"])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--tag", default="final")
    ap.add_argument("--geo", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--external", nargs="*", default=[])
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    if args.stage == "prepare":
        prepare(args.dir, args.root, args.tag, args.geo, args.jobs)
    elif args.stage == "external":
        external(args.dir)
    else:
        report(args.dir, args.external, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
