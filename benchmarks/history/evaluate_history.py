"""Pre-merger address study (PROTOCOL.md): addresses written as they were in 2006 and 2011.

Stages, each run once:

  inputs    builds the inputs and the answer key (the facility's point in the 2026-01-01 boundaries)
                                                     -> DIR/inputs.jsonl, DIR/summary.json
  jaden     JADEN's rules on every input              -> DIR/jaden.jsonl
  reverse   jaden.history.former_municipality on the eligible P02 facilities -> DIR/reverse.jsonl
  external  the inputs for the other tools (all changed, 5,000 unchanged per source, seed 2026)
                                                     -> DIR/external_inputs.jsonl
  report    everything scored                         -> results/report.md, results/scores.json

Usage:
    python benchmarks/history/evaluate_history.py inputs   --dir DIR
    python benchmarks/history/evaluate_history.py jaden    --dir DIR [--jobs 3]
    python benchmarks/history/evaluate_history.py reverse  --dir DIR
    python benchmarks/history/evaluate_history.py external --dir DIR
    (run benchmarks/jabench/baselines/jageocoder_run.py and geolonia_run.mjs on DIR/external_inputs.jsonl)
    python benchmarks/history/evaluate_history.py report   --dir DIR --external geolonia=... jageocoder=...
"""

import argparse
import json
import math
import random
import re
import struct
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
for p in ("src", "benchmarks/registers", "benchmarks/jabench/baselines"):
    sys.path.insert(0, str(ROOT / p))

DATA = Path.home() / ".cache" / "jaden-realdata"
SOURCES = ("P02-06", "P14-11")
SAMPLE_UNCHANGED = 5000


def read_points(shp: bytes) -> List[Optional[Tuple[float, float]]]:
    """Point (type 1) records of a .shp file as (lon, lat); None for other or empty records."""
    out: List[Optional[Tuple[float, float]]] = []
    pos = 100
    while pos < len(shp):
        _, length = struct.unpack(">ii", shp[pos:pos + 8])
        content = shp[pos + 8: pos + 8 + 2 * length]
        pos += 8 + 2 * length
        if struct.unpack("<i", content[:4])[0] == 1:
            out.append(struct.unpack("<2d", content[4:20]))
        else:
            out.append(None)
    return out


def _zip_rows(path: Path) -> Iterator[Tuple[Dict[str, str], Optional[Tuple[float, float]]]]:
    from jaden.data.build_former import read_dbf
    with zipfile.ZipFile(path) as zf:
        dbf = next(n for n in zf.namelist() if n.lower().endswith(".dbf"))
        shp = next(n for n in zf.namelist() if n.lower().endswith(".shp"))
        rows = read_dbf(zf.read(dbf))
        points = read_points(zf.read(shp))
    yield from zip(rows, points)


# ---------------------------------------------------------------------------------------------- inputs
def _fold(text: str) -> str:
    from geolonia_to_jsonl import fold
    return fold(text)


def _current_names() -> Dict[str, set]:
    from jaden.data.loader import get_registry
    names: Dict[str, set] = defaultdict(set)
    for m in get_registry().list_municipalities():
        names[m.prefecture_name].add(_fold(m.name))
        if m.city:
            names[m.prefecture_name].add(_fold(m.city))
    return names


def _change_kind(reason: str, successors: Tuple[str, ...], name: str) -> str:
    if len(successors) > 1:
        return "split"
    if "区" in name and ("政令" in reason or "行政区" in reason or name.endswith("区")):
        return "ward"
    if "合併" in reason:
        return "merger"
    if any(k in reason for k in ("市制", "町制", "名称", "移行")):
        return "status or name change"
    return "other"


def stage_inputs(folder: Path) -> None:
    from jaden.data.build_former import _check_digit, inside
    from jaden.data.loader import get_registry
    from jaden.history import code_change
    from audit_registers import _boundaries
    reg = get_registry()
    cache = folder / "n03-2026"
    shapes: Dict[int, List[Any]] = {}

    def locate(lon: float, lat: float, hint: int) -> Optional[str]:
        if not (20 < lat < 46 and 122 < lon < 154):
            return None
        for p in [hint] + [q for q in range(1, 48) if q != hint]:
            if p not in shapes:
                shapes[p] = _boundaries(p, cache)
            for code, b, rings in shapes[p]:
                if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and inside(lon, lat, rings):
                    return code
        return None

    pref_name = {p.code: p.name for p in reg.list_all_prefectures()}
    pref_code = {v: k for k, v in pref_name.items()}
    current = _current_names()
    counts: Counter = Counter()
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "inputs.jsonl", "w", encoding="utf-8") as fh:
        for path in sorted((DATA / "p02").glob("P02-06_*_GML.zip")):
            for i, (row, point) in enumerate(_zip_rows(path)):
                addr = row.get("P02_005", "").strip()
                counts["P02-06 rows"] += 1
                if not addr:
                    continue
                code6 = row["P02_001"] + _check_digit(row["P02_001"])
                rec = reg.get_municipality_by_code(code6)
                if rec is not None:
                    then, changed, kind = rec.name, False, ""
                else:
                    ch = code_change(code6)
                    if ch is None:
                        counts["P02-06 excluded: code unknown"] += 1
                        continue
                    then = ch.name
                    if then.endswith("区") and "市" not in then and ch.successors:
                        succ = reg.get_municipality_by_code(ch.successors[0])
                        then = (succ.city or "") + then if succ else then
                    changed, kind = True, _change_kind(ch.reason, ch.successors, then)
                truth = locate(point[0], point[1], int(code6[:2])) if point else None
                if truth is None:
                    counts["P02-06 excluded: no usable point"] += 1
                    continue
                pref = pref_name[code6[:2]]
                text = pref + then + addr
                counts[f"P02-06 {'changed' if changed else 'unchanged'}"] += 1
                fh.write(json.dumps({"id": f"{path.stem[:9]}:{i}", "source": "P02-06", "input": text,
                                     "changed": changed, "kind": kind, "then_code": code6, "then_name": then,
                                     "truth": truth}, ensure_ascii=False) + "\n")
        for path in sorted((DATA / "p14-11").glob("P14-11_*_GML.zip")):
            for i, (row, point) in enumerate(_zip_rows(path)):
                addr = row.get("P14_003", "").strip()
                counts["P14-11 rows"] += 1
                if not addr:
                    continue
                pref, muni = row["P14_001"].strip(), row["P14_002"].strip()
                bare = re.sub(r"^.+?郡", "", muni)
                changed = _fold(bare) not in current.get(pref, set())
                kind = ""
                if changed:
                    from jaden.data.former import get_former_municipalities
                    found = get_former_municipalities().match(bare, pref_code.get(pref))
                    succ = tuple(sorted({s for f in found[0] for s in f.successors})) if found else ()
                    kind = "split" if len(succ) > 1 else ("ward" if bare.endswith("区") else
                                                         "status or name change" if bare[:-1] and any(
                                                             _fold(bare[:-1]) + s in current.get(pref, set()) for s in "市町村")
                                                         else "merger")
                truth = locate(point[0], point[1], int(pref_code.get(pref, "13"))) if point else None
                if truth is None:
                    counts["P14-11 excluded: no usable point"] += 1
                    continue
                counts[f"P14-11 {'changed' if changed else 'unchanged'}"] += 1
                fh.write(json.dumps({"id": f"{path.stem[:9]}:{i}", "source": "P14-11", "input": pref + muni + addr,
                                     "changed": changed, "kind": kind, "then_code": "", "then_name": muni,
                                     "truth": truth}, ensure_ascii=False) + "\n")
    (folder / "summary.json").write_text(json.dumps(dict(counts), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------------------------- jaden
def _jaden_batch(batch: List[Dict[str, Any]]) -> List[str]:
    import jaden
    out = []
    for r in batch:
        v = jaden.validate(r["input"])
        out.append(json.dumps({"id": r["id"], "status": v.status, "lg_code": v.lg_code if v.status == "ACCEPTED" else None}))
    return out


def stage_jaden(folder: Path, jobs: int) -> None:
    rows = [json.loads(line) for line in open(folder / "inputs.jsonl", encoding="utf-8")]
    batches = [rows[i:i + 2000] for i in range(0, len(rows), 2000)]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    with get_context("spawn").Pool(jobs) as pool, open(folder / "jaden.jsonl", "w", encoding="utf-8") as fh:
        for part in pool.imap(_jaden_batch, batches):
            fh.write("\n".join(part) + "\n")
    (folder / "jaden_commit.txt").write_text(commit, encoding="utf-8")
    print(f"{len(rows):,} inputs at {commit}", file=sys.stderr)


# --------------------------------------------------------------------------------------------- reverse
def stage_reverse(folder: Path) -> None:
    import jaden
    from jaden.history import former_municipality, _HISTORY
    eligible = 0
    with open(folder / "reverse.jsonl", "w", encoding="utf-8") as fh:
        for line in open(folder / "inputs.jsonl", encoding="utf-8"):
            r = json.loads(line)
            if r["source"] != "P02-06" or not r["changed"] or _HISTORY.former(r["then_code"]) is None:
                continue
            eligible += 1
            f = former_municipality(jaden.normalize(r["input"]))
            fh.write(json.dumps({"id": r["id"], "expected": r["then_code"], "got": f.code if f else None}) + "\n")
    print(f"{eligible:,} eligible facilities", file=sys.stderr)


# -------------------------------------------------------------------------------------------- external
def stage_external(folder: Path) -> None:
    rows = [json.loads(line) for line in open(folder / "inputs.jsonl", encoding="utf-8")]
    chosen = [r for r in rows if r["changed"]]
    for src in SOURCES:
        pool = sorted((r for r in rows if r["source"] == src and not r["changed"]), key=lambda r: r["id"])
        chosen += random.Random(2026).sample(pool, min(SAMPLE_UNCHANGED, len(pool)))
    with open(folder / "external_inputs.jsonl", "w", encoding="utf-8") as fh:
        for r in chosen:
            fh.write(json.dumps({"id": r["id"], "input": r["input"]}, ensure_ascii=False) + "\n")
    print(f"{len(chosen):,} inputs for the other tools", file=sys.stderr)


# ---------------------------------------------------------------------------------------------- report
def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def stage_report(folder: Path, externals: List[str], out: Path) -> None:
    from jaden.audit import _same_place
    rows = {r["id"]: r for r in map(json.loads, open(folder / "inputs.jsonl", encoding="utf-8"))}
    systems: Dict[str, Dict[str, Optional[str]]] = {
        "JADEN rules": {r["id"]: r["lg_code"] for r in map(json.loads, open(folder / "jaden.jsonl", encoding="utf-8"))}}
    for e in externals:
        name, _, path = e.partition("=")
        systems[name] = {r["id"]: r.get("lg_code") for r in map(json.loads, open(path, encoding="utf-8"))}
    ext_ids = {json.loads(line)["id"] for line in open(folder / "external_inputs.jsonl", encoding="utf-8")}

    def score(ids: List[str], answers: Dict[str, Optional[str]]) -> Dict[str, Any]:
        right = wrong = 0
        for i in ids:
            a = answers.get(i)
            if a and not a.startswith("unknown"):
                if _same_place(a, rows[i]["truth"]):
                    right += 1
                else:
                    wrong += 1
            elif a:
                wrong += 1      # a municipality that no longer exists
        n = len(ids)
        lo, hi = wilson(wrong, right + wrong)
        return {"n": n, "right": right, "wrong": wrong, "answered": right + wrong, "wrong_ci": [lo, hi]}

    table: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    kinds: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for src in SOURCES:
        for setname, flag in (("changed", True), ("unchanged", False)):
            ids_all = [i for i, r in rows.items() if r["source"] == src and r["changed"] == flag]
            ids_ext = [i for i in ids_all if i in ext_ids]
            for sname, answers in systems.items():
                ids = ids_all if sname == "JADEN rules" else ids_ext
                table[f"{src} {setname}"][sname] = score(ids, answers)
                if sname == "JADEN rules" and ids_all != ids_ext:
                    table[f"{src} {setname}"]["JADEN rules (same sample as the other tools)"] = score(ids_ext, answers)
            if flag:
                by_kind: Dict[str, List[str]] = defaultdict(list)
                for i in ids_all:
                    by_kind[rows[i]["kind"] or "other"].append(i)
                for k, ids in by_kind.items():
                    kinds[src][k] = {s: score([i for i in ids if s == "JADEN rules" or i in ext_ids], a)
                                     for s, a in systems.items()}
    reverse = [json.loads(line) for line in open(folder / "reverse.jsonl", encoding="utf-8")] \
        if (folder / "reverse.jsonl").exists() else []
    rev_agree = sum(1 for r in reverse if r["got"] == r["expected"])
    rev_none = sum(1 for r in reverse if r["got"] is None)

    def h(cell: Dict[str, Any]) -> Tuple[float, float, float]:
        return cell["right"] / max(1, cell["n"]), cell["wrong"] / max(1, cell["answered"]), cell["wrong_ci"][1]

    jc, jw = table["P02-06 changed"]["JADEN rules"], table["P14-11 changed"]["JADEN rules"]
    hyp = {
        "H1": h(jc)[0] >= 0.95 and h(jc)[1] <= 0.01,
        "H2": h(jw)[0] >= 0.95 and h(jw)[1] <= 0.01,
        "H3": all(
            (lambda own, other: own["wrong"] / max(1, own["answered"]) < other["wrong"] / max(1, other["answered"])
             and own["right"] / max(1, own["n"]) >= other["right"] / max(1, other["n"]))(
                table[f"{s} changed"]["JADEN rules"], table[f"{s} changed"][e]) for s in SOURCES for e in systems
            if e != "JADEN rules") if len(systems) > 1 else None,
        "H4": all(h(table[f"{s} unchanged"]["JADEN rules"])[0] >= 0.99 and h(table[f"{s} unchanged"]["JADEN rules"])[1] <= 0.001
                  for s in SOURCES),
        "H5": (rev_agree / len(reverse) >= 0.97) if reverse else None,
    }
    commit = (folder / "jaden_commit.txt").read_text().strip() if (folder / "jaden_commit.txt").exists() else ""
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    lines = ["# Pre-merger address study", "",
             f"Run under `benchmarks/history/PROTOCOL.md`; JADEN at `{commit[:10]}`. Right / wrong: answers naming the "
             "municipality that contains the facility's point in the 2026-01-01 boundaries, or another one. The other "
             f"tools ran on every changed input and {SAMPLE_UNCHANGED:,} unchanged inputs per source.", "",
             "## Inputs", ""] + [f"- {k}: {v:,}" for k, v in summary.items()] + ["", "## Hypotheses", ""]
    lines += [f"- **{k}**: {'holds' if v else 'does not hold' if v is not None else 'not tested'}" for k, v in hyp.items()]
    lines += ["", "## Results", "", "| Set | System | Inputs | Right | Wrong | Wrong among answers (95% CI) | No answer |",
              "| :--- | :--- | ---: | ---: | ---: | :--- | ---: |"]
    for setname, cells in table.items():
        for i, (s, c) in enumerate(cells.items()):
            lo, hi = c["wrong_ci"]
            lines.append(f"| {setname if i == 0 else ''} | {s} | {c['n']:,} | {100 * c['right'] / max(1, c['n']):.2f}% | "
                         f"{c['wrong']:,} | {100 * c['wrong'] / max(1, c['answered']):.2f}% ({100 * lo:.2f}–{100 * hi:.2f}%) | "
                         f"{100 * (c['n'] - c['answered']) / max(1, c['n']):.2f}% |")
    lines += ["", "## Changed inputs by kind of change", "", "| Source | Kind | System | Inputs | Right | Wrong |",
              "| :--- | :--- | :--- | ---: | ---: | ---: |"]
    for src, by in kinds.items():
        for k, cells in sorted(by.items()):
            for s, c in cells.items():
                lines.append(f"| {src} | {k} | {s} | {c['n']:,} | {100 * c['right'] / max(1, c['n']):.1f}% | {c['wrong']:,} |")
    lines += ["", "## Reverse lookup (P02-06, retired 2006 codes that were also the 2000 code)", "",
              f"- eligible facilities: {len(reverse):,}",
              f"- former_municipality agrees with the 2006 code: {rev_agree:,} ({100 * rev_agree / max(1, len(reverse)):.2f}%)",
              f"- no former municipality returned: {rev_none:,}"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.json").write_text(json.dumps({"commit": commit, "table": table, "kinds": kinds, "hypotheses": hyp,
                                                 "reverse": {"n": len(reverse), "agree": rev_agree, "none": rev_none},
                                                 "inputs": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["inputs", "jaden", "reverse", "external", "report"])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--external", nargs="*", default=[])
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    {"inputs": lambda: stage_inputs(args.dir), "jaden": lambda: stage_jaden(args.dir, args.jobs),
     "reverse": lambda: stage_reverse(args.dir), "external": lambda: stage_external(args.dir),
     "report": lambda: stage_report(args.dir, args.external, args.out)}[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
