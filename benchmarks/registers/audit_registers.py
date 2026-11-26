"""Register consistency study (PROTOCOL.md): JADEN's audit on four public registers.

Stages, each run once, writing to DIR (a scratch folder) and, for the report, to results/:

  audit     every record through jaden.audit.check_record          -> DIR/<register>.audit.json
  locate    the published point of flagged records and of a sample of consistent ones, placed in the
            2026-01-01 municipal boundaries (N03-2026)               -> DIR/<register>.locate.json
  reader2   jageocoder on conflict records whose address writes its municipality
                                                                      -> DIR/reader2_in.jsonl (run jageocoder on it)
  sample    the inspection samples (seed 2027)                       -> results/inspection.csv (filled in by hand)
  report    everything together                                      -> results/report.md, results/scores.json

Usage:
    python benchmarks/registers/audit_registers.py audit  --dir DIR [--registers nta care medical welfare] [--jobs 3]
    python benchmarks/registers/audit_registers.py locate --dir DIR
    python benchmarks/registers/audit_registers.py reader2 --dir DIR
    python benchmarks/registers/audit_registers.py sample --dir DIR
    python benchmarks/registers/audit_registers.py report --dir DIR [--reader2 jageocoder.jsonl]
"""

import argparse
import csv
import hashlib
import json
import math
import random
import subprocess
import sys
import zipfile
from collections import Counter
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
for p in ("src", "benchmarks/realdata"):
    sys.path.insert(0, str(ROOT / p))

DATA = Path.home() / ".cache" / "jaden-realdata"
REGISTERS = ("nta", "care", "medical", "welfare")
TITLES = {"nta": "NTA corporations (2026-10-30)", "care": "MHLW care offices (2026-06)",
          "medical": "MHLW medical facilities (2026-06-01)", "welfare": "MLIT welfare facilities P14 (2023)"}
FLAGGED = ("conflict", "district_not_in_claimed", "code_retired", "code_invalid")
CONSISTENT = ("consistent", "consistent_former_name", "code_retired")
BASELINE_SAMPLE = 2000
N03_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2026/N03-20260101_{pref:02d}_GML.zip"
CONFLICT_SAMPLE, DISTRICT_SAMPLE = 100, 50

Record = Tuple[str, str, str, str, str]   # id, address, code, lat, lon


# ------------------------------------------------------------------------------------------- readers
def records(register: str) -> Iterator[Record]:
    if register == "nta":
        import evaluate_companies
        zips = sorted((DATA / "companies").glob("*.zip"))
        for number, pref, city, street, code5, _postal in evaluate_companies.read_rows(zips[-1]):
            yield number, pref + city + street, code5, "", ""
    elif register == "care":
        import evaluate_care
        for ident, _pref, _city, address, _kata, code, lat, lon, _office in evaluate_care.read_rows(DATA / "care"):
            yield ident, address, code, lat, lon
    elif register == "medical":
        sys.path.insert(0, str(ROOT / "benchmarks" / "heldout2"))
        import importlib
        sys.modules.pop("make_inputs", None)
        med = importlib.import_module("make_inputs")
        for r in med.rows(DATA):
            code = r["pref"].zfill(2) + r["muni"].zfill(3) if len(r["muni"]) == 3 else ""
            yield r["key"], r["address"], code, r["lat"], r["lon"]
    elif register == "welfare":
        sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))
        import importlib
        sys.modules.pop("make_inputs", None)
        wel = importlib.import_module("make_inputs")
        for r in wel.rows(DATA / "welfare" / "P14-23_GML.zip"):
            yield r["key"], r["address"], r["truth"], str(r["lat"]), str(r["lon"])
    else:
        raise ValueError(register)


def chunks(it: Iterator[Record], n: int) -> Iterator[List[Record]]:
    batch: List[Record] = []
    for x in it:
        batch.append(x)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch


def _has_point(lat: str, lon: str) -> bool:
    """Coordinates are given (some rows carry 0.0 for a missing point)."""
    try:
        return float(lat) != 0.0 and float(lon) != 0.0
    except (TypeError, ValueError):
        return False


def _baseline_pick(ident: str) -> int:
    return int(hashlib.md5(ident.encode("utf-8")).hexdigest()[:8], 16)


# --------------------------------------------------------------------------------------------- audit
def _audit_batch(batch: List[Record]) -> Tuple[Counter, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    from jaden.audit import check_record
    counts: Counter = Counter()
    flagged, formers, baseline = [], [], []
    for ident, address, code, lat, lon in batch:
        r = check_record(address, code or None)
        counts[(r.verdict, r.municipality_written, bool(r.former_name), r.code_status)] += 1
        rec = {"id": ident, "address": address, "code": r.claimed_code, "verdict": r.verdict,
               "code_status": r.code_status, "resolved": r.resolved_code, "suggested": r.suggested_code,
               "candidates": list(r.candidates[:10]), "n_candidates": len(r.candidates),
               "former_name": r.former_name, "written": r.municipality_written,
               "both_written": r.claimed_name_in_address, "detail": r.detail, "lat": lat, "lon": lon}
        if r.verdict in FLAGGED:
            flagged.append(rec)
        elif r.former_name and len(formers) < 200:
            formers.append(rec)
        elif r.verdict == "consistent" and _has_point(lat, lon) and _baseline_pick(ident) % 50 == 0:
            baseline.append(rec)
    return counts, flagged, formers, baseline


def stage_audit(folder: Path, registers: List[str], jobs: int, limit: int = 0) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    ctx = get_context("spawn")
    for reg in registers:
        counts: Counter = Counter()
        flagged: List[Dict[str, Any]] = []
        formers: List[Dict[str, Any]] = []
        baseline: List[Dict[str, Any]] = []
        n = 0
        with ctx.Pool(jobs) as pool:
            source = records(reg)
            if limit:                      # a dry run on the first records only; never used for the reported run
                import itertools
                source = itertools.islice(source, limit)
            for c, f, fo, b in pool.imap(_audit_batch, chunks(source, 5000 if not limit else 100)):
                counts.update(c)
                flagged += f
                formers += fo
                baseline += b
                n += sum(c.values())
                if n % 500000 < 5000:
                    print(f"  {reg}: {n:,}", file=sys.stderr, flush=True)
        baseline.sort(key=lambda r: _baseline_pick(r["id"]))
        random.Random(2026).shuffle(baseline)
        out = {"register": reg, "records": n,
               "counts": [{"verdict": v, "written": w, "former": f, "code_status": s, "n": k}
                          for (v, w, f, s), k in sorted(counts.items(), key=lambda x: -x[1])],
               "flagged": flagged, "former_examples": formers[:200], "baseline": baseline[:BASELINE_SAMPLE]}
        (folder / f"{reg}.audit.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"{reg}: {n:,} records, {len(flagged):,} flagged, baseline {len(out['baseline']):,}", file=sys.stderr)


# -------------------------------------------------------------------------------------------- locate
def _boundaries(pref: int, cache: Path) -> List[Tuple[str, Tuple[float, float, float, float], Any]]:
    import urllib.request
    from jaden.data.build_former import _check_digit, read_dbf, read_polygons
    cache.mkdir(parents=True, exist_ok=True)
    url = N03_URL.format(pref=pref)
    target = cache / url.rsplit("/", 1)[-1]
    if not target.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "jaden-research"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            target.write_bytes(resp.read())
    with zipfile.ZipFile(target) as zf:
        shp = next(n for n in zf.namelist() if n.endswith(".shp"))
        dbf = next(n for n in zf.namelist() if n.endswith(".dbf"))
        cpg = next((n for n in zf.namelist() if n.endswith(".cpg")), None)
        enc = zf.read(cpg).decode("ascii").strip().lower() if cpg else "cp932"
        polygons = read_polygons(zf.read(shp))
        rows = read_dbf(zf.read(dbf), "utf-8" if "utf" in enc else "cp932")
    out = []
    for (bbox, rings), row in zip(polygons, rows):
        code = (row.get("N03_007") or "").strip()
        if code and rings:
            out.append((code + _check_digit(code), bbox, rings))
    return out


def stage_locate(folder: Path) -> None:
    from jaden.data.build_former import inside
    cache = folder / "n03-2026"
    shapes: Dict[int, List[Any]] = {}

    def locate(lat: str, lon: str, hint_pref: str) -> Optional[str]:
        try:
            y, x = float(lat), float(lon)
        except (TypeError, ValueError):
            return None
        if not (20 < y < 46 and 122 < x < 154):
            return None
        order = [int(hint_pref)] if hint_pref.isdigit() and 1 <= int(hint_pref) <= 47 else []
        order += [p for p in range(1, 48) if p not in order]
        for p in order:
            if p not in shapes:
                shapes[p] = _boundaries(p, cache)
            for code, b, rings in shapes[p]:
                if b[0] <= x <= b[2] and b[1] <= y <= b[3] and inside(x, y, rings):
                    return code
        return None

    for reg in REGISTERS:
        path = folder / f"{reg}.audit.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        found = {}
        for rec in data["flagged"] + data["baseline"]:
            if rec.get("lat"):
                found[rec["id"]] = locate(rec["lat"], rec["lon"], (rec["code"] or "")[:2])
        (folder / f"{reg}.locate.json").write_text(json.dumps(found), encoding="utf-8")
        print(f"{reg}: located {sum(1 for v in found.values() if v):,} of {len(found):,}", file=sys.stderr)


# ------------------------------------------------------------------------------------------- reader2
def stage_reader2(folder: Path) -> None:
    with open(folder / "reader2_in.jsonl", "w", encoding="utf-8") as fh:
        for reg in REGISTERS:
            path = folder / f"{reg}.audit.json"
            if not path.exists():
                continue
            for rec in json.loads(path.read_text(encoding="utf-8"))["flagged"]:
                if rec["verdict"] == "conflict" and rec["written"]:
                    fh.write(json.dumps({"id": f"{reg}|{rec['id']}", "input": rec["address"]}, ensure_ascii=False) + "\n")
    print(f"wrote {folder / 'reader2_in.jsonl'}; run benchmarks/jabench/baselines/jageocoder_run.py on it", file=sys.stderr)


# -------------------------------------------------------------------------------------------- sample
def _name(code: Optional[str]) -> str:
    from jaden.data.loader import get_registry
    if not code:
        return ""
    rec = get_registry().get_municipality_by_code(code)
    if rec is not None:
        return f"{rec.prefecture_name}{rec.name}"
    from jaden.history import code_change
    ch = code_change(code)
    return f"(retired) {ch.name}" if ch else "(unknown)"


def stage_sample(folder: Path, out: Path) -> None:
    rows = []
    for reg in REGISTERS:
        path = folder / f"{reg}.audit.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        located = json.loads((folder / f"{reg}.locate.json").read_text(encoding="utf-8")) \
            if (folder / f"{reg}.locate.json").exists() else {}
        rng = random.Random(2027)
        for verdict, size in (("conflict", CONFLICT_SAMPLE), ("district_not_in_claimed", DISTRICT_SAMPLE)):
            pool = sorted((r for r in data["flagged"] if r["verdict"] == verdict), key=lambda r: r["id"])
            for rec in rng.sample(pool, min(size, len(pool))):
                loc = located.get(rec["id"])
                rows.append({"register": reg, "id": rec["id"], "verdict": verdict, "address": rec["address"],
                             "code": rec["code"], "code_name": _name(rec["code"]),
                             "jaden": rec["resolved"] or "", "jaden_name": _name(rec["resolved"]),
                             "n_candidates": rec["n_candidates"], "written": rec["written"],
                             "point_in": loc or "", "point_name": _name(loc),
                             "category": "", "reason": ""})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} records to inspect -> {out}", file=sys.stderr)


# -------------------------------------------------------------------------------------------- report
def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _same(a: Optional[str], b: Optional[str]) -> bool:
    if not a or not b:
        return False
    from jaden.audit import _same_place
    from jaden.history import current_codes
    return any(_same_place(a, c) for c in (current_codes(b) or (b,)))


def stage_report(folder: Path, out: Path, reader2: Optional[Path]) -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    second = {}
    if reader2 and reader2.exists():
        second = {r["id"]: r.get("lg_code") for r in map(json.loads, open(reader2, encoding="utf-8"))}
    inspected: List[Dict[str, str]] = []
    if (out / "inspection.csv").exists():
        inspected = list(csv.DictReader(open(out / "inspection.csv", encoding="utf-8")))
    scores: Dict[str, Any] = {"commit": commit, "registers": {}}
    lines = ["# Register consistency study", "",
             f"Run under `benchmarks/registers/PROTOCOL.md` with JADEN at `{commit}`. Shares are of all records of the "
             "register (or of those whose address writes its municipality); intervals are Wilson 95%.", ""]
    verdicts = ("consistent", "consistent_former_name", "code_retired", "conflict", "district_not_in_claimed",
                "undetermined", "unreadable", "code_invalid")
    lines += ["## Verdicts", "", "| Register | Records | " + " | ".join(verdicts) + " |",
              "| :--- | ---: |" + " ---: |" * len(verdicts)]
    for reg in REGISTERS:
        path = folder / f"{reg}.audit.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        n = data["records"]
        by_v: Counter = Counter()
        by_v_written: Counter = Counter()
        written_n = 0
        former_n = 0
        retired_code_n = 0
        for c in data["counts"]:
            by_v[c["verdict"]] += c["n"]
            if c["written"]:
                by_v_written[c["verdict"]] += c["n"]
                written_n += c["n"]
            if c["former"]:
                former_n += c["n"]
            if c["code_status"] == "retired":
                retired_code_n += c["n"]
        consistent_written = sum(by_v_written[v] for v in CONSISTENT)
        lo, hi = wilson(consistent_written, written_n)
        s = {"records": n, "verdicts": dict(by_v), "written": written_n, "verdicts_written": dict(by_v_written),
             "consistent_written_share": consistent_written / max(1, written_n), "consistent_written_ci": [lo, hi],
             "former_name_records": former_n, "retired_code_records": retired_code_n}
        lines.append(f"| {TITLES[reg]} | {n:,} | " + " | ".join(f"{by_v[v]:,}" for v in verdicts) + " |")
        # location signal
        locp = folder / f"{reg}.locate.json"
        if locp.exists():
            located = json.loads(locp.read_text(encoding="utf-8"))
            base = [r for r in data["baseline"] if located.get(r["id"])]
            agree = sum(1 for r in base if _same(located[r["id"]], r["code"]))
            s["baseline_point_agrees"] = [agree, len(base)]
            flag_loc: Counter = Counter()
            for r in data["flagged"]:
                if r["verdict"] != "conflict" or not located.get(r["id"]):
                    continue
                p = located[r["id"]]
                in_code, in_text = _same(p, r["code"]), _same(p, r["resolved"])
                flag_loc["point in code's municipality" if in_code and not in_text else
                         "point in text's municipality" if in_text and not in_code else
                         "point in both" if in_code and in_text else "point in neither"] += 1
            s["conflict_point"] = dict(flag_loc)
        if second:
            agree2 = Counter()
            for r in data["flagged"]:
                if r["verdict"] == "conflict" and r["written"]:
                    j = second.get(f"{reg}|{r['id']}")
                    agree2["jageocoder agrees with JADEN" if _same(j, r["resolved"]) else
                           "jageocoder agrees with the code" if _same(j, r["code"]) else
                           "jageocoder gives neither" if j else "jageocoder gives no answer"] += 1
            s["conflict_reader2"] = dict(agree2)
        scores["registers"][reg] = s
    lines += ["", "## Records whose address writes its municipality", "",
              "| Register | Such records | Consistent (incl. former name, retired code) | 95% CI | Conflict | Code retired | Address uses a former name |",
              "| :--- | ---: | ---: | :--- | ---: | ---: | ---: |"]
    for reg, s in scores["registers"].items():
        vw = s["verdicts_written"]
        lo, hi = s["consistent_written_ci"]
        lines.append(f"| {TITLES[reg]} | {s['written']:,} | {100 * s['consistent_written_share']:.3f}% | "
                     f"{100 * lo:.3f}–{100 * hi:.3f}% | {vw.get('conflict', 0):,} | {vw.get('code_retired', 0):,} | "
                     f"{s['former_name_records']:,} |")
    lines += ["", "## Location signal (published coordinates in the 2026-01-01 boundaries)", "",
              "| Register | Sampled consistent records: point in the code's municipality | Conflicts: point in code's / text's / both / neither |",
              "| :--- | :--- | :--- |"]
    for reg, s in scores["registers"].items():
        if "baseline_point_agrees" in s:
            a, b = s["baseline_point_agrees"]
            lo, hi = wilson(a, b)
            cp = s.get("conflict_point", {})
            lines.append(f"| {TITLES[reg]} | {a:,} of {b:,} ({100 * a / max(1, b):.1f}%, {100 * lo:.1f}–{100 * hi:.1f}%) | "
                         f"{cp.get('point in code' + chr(39) + 's municipality', 0)} / {cp.get('point in text' + chr(39) + 's municipality', 0)} / "
                         f"{cp.get('point in both', 0)} / {cp.get('point in neither', 0)} |")
    if second:
        lines += ["", "## Second reader on conflicts whose address writes its municipality (jageocoder)", "",
                  "| Register | Agrees with JADEN | Agrees with the code | Neither | No answer |", "| :--- | ---: | ---: | ---: | ---: |"]
        for reg, s in scores["registers"].items():
            a = s.get("conflict_reader2", {})
            lines.append(f"| {TITLES[reg]} | {a.get('jageocoder agrees with JADEN', 0)} | {a.get('jageocoder agrees with the code', 0)} | "
                         f"{a.get('jageocoder gives neither', 0)} | {a.get('jageocoder gives no answer', 0)} |")
    if inspected and any(r["category"] for r in inspected):
        lines += ["", "## Inspection (categories defined in the protocol)", "",
                  "| Register | Verdict | Inspected | C code wrong | T text wrong | R reading wrong | G gazetteer gap | U cannot tell |",
                  "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        groups: Dict[Tuple[str, str], Counter] = {}
        for r in inspected:
            groups.setdefault((r["register"], r["verdict"]), Counter())[r["category"]] += 1
        for (reg, verdict), c in groups.items():
            total = sum(c.values())
            lines.append(f"| {TITLES[reg]} | {verdict} | {total} | " + " | ".join(str(c.get(k, 0)) for k in "CTRGU") + " |")
        scores["inspection"] = {f"{k[0]}|{k[1]}": dict(v) for k, v in groups.items()}
    # Pre-registered hypotheses
    regs = scores["registers"]
    retired_share = {r: s["retired_code_records"] / max(1, s["records"]) for r, s in regs.items()}
    h3: Dict[str, Any] = {}
    for reg in REGISTERS:
        sel = [r for r in inspected if r["register"] == reg and r["verdict"] == "conflict" and r["written"] == "True"]
        if len(sel) >= 20:
            k = sum(1 for r in sel if r["category"] == "R")
            h3[reg] = [k, len(sel)]
    hyp = {
        "H1": all(s["consistent_written_share"] >= 0.995 for s in regs.values() if s["written"]),
        "H2": max(retired_share, key=lambda r: retired_share[r]) == "welfare",
        "H3": all(k / n <= 0.20 for k, n in h3.values()) if h3 else None,
        "H4": all(s["baseline_point_agrees"][0] / max(1, s["baseline_point_agrees"][1]) >= 0.97
                  for s in regs.values() if s.get("baseline_point_agrees", [0, 0])[1] > 0),   # registers with coordinates
    }
    scores["hypotheses"] = hyp
    scores["h3_reading_errors"] = h3
    scores["retired_share"] = retired_share
    lines += ["", "## Hypotheses", ""]
    lines += [f"- **{k}**: {'holds' if v else 'does not hold' if v is not None else 'not tested'}" for k, v in hyp.items()]
    lines += ["  - H1, consistent share of records that write their municipality: " +
              ", ".join(f"{TITLES[r]} {100 * s['consistent_written_share']:.3f}%" for r, s in regs.items() if s["written"]),
              "  - H2, share of records with a retired code: " +
              ", ".join(f"{TITLES[r]} {100 * v:.3f}%" for r, v in retired_share.items()),
              "  - H3, reading errors among inspected conflicts whose address writes its municipality: " +
              ", ".join(f"{TITLES[r]} {k} of {n}" for r, (k, n) in h3.items())]
    # Exploratory: codes that recur among conflicts (a code used for offices elsewhere)
    lines += ["", "## Exploratory: codes that recur among conflicts", "",
              "| Register | Code | Municipality | Conflicts with this code | Of them, point in the text's municipality |",
              "| :--- | :--- | :--- | ---: | ---: |"]
    for reg in REGISTERS:
        path = folder / f"{reg}.audit.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        locp = folder / f"{reg}.locate.json"
        located = json.loads(locp.read_text(encoding="utf-8")) if locp.exists() else {}
        by_code = Counter(r["code"] for r in data["flagged"] if r["verdict"] == "conflict")
        for code, k in by_code.most_common(3):
            if k < 5:
                continue
            in_text = sum(1 for r in data["flagged"] if r["verdict"] == "conflict" and r["code"] == code
                          and located.get(r["id"]) and _same(located[r["id"]], r["resolved"]))
            lines.append(f"| {TITLES[reg]} | {code} | {_name(code)} | {k} | {in_text} |")
    (out / "scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["audit", "locate", "reader2", "sample", "report"])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--registers", nargs="*", default=list(REGISTERS))
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--reader2", type=Path)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--limit", type=int, default=0, help="dry run on the first N records of each register")
    args = ap.parse_args()
    if args.stage == "audit":
        stage_audit(args.dir, args.registers, args.jobs, args.limit)
    elif args.stage == "locate":
        stage_locate(args.dir)
    elif args.stage == "reader2":
        stage_reader2(args.dir)
    elif args.stage == "sample":
        stage_sample(args.dir, args.out / "inspection.csv")
    else:
        stage_report(args.dir, args.out, args.reader2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
