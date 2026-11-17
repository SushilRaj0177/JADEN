"""Real-data evaluation on the registered addresses of every active corporation in Japan.

Source: National Tax Agency Corporate Number Publication Site, full download (CSV, Unicode).
Each row has the registered address as three fields (prefecture, municipality, the rest as
registered), the municipality code and the postal code. None of it comes from the data JADEN
resolves with, so it is an independent answer key:

  municipality   JADEN's code against the row's own code
  town           the town JADEN resolves against the row's postal code (Japan Post area codes)
  rejections     every row is a real registered address; a rejection is JADEN's failure

Three inputs are built from each row: the full address, the address without its prefecture,
and the full address with its postal code in front.

Usage:
    python benchmarks/realdata/download.py companies
    python benchmarks/realdata/evaluate_companies.py [--every 20] [--jobs 4] [--dump failures.jsonl]
"""

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import common
from common import DEFAULT_DATA, Tally, municipality_outcome, outcome_table, pct, resolve, run_pool, table

Item = Tuple[str, str, str, str, str, str]
_POSTAL_INDEX: Optional[Dict[str, List[Tuple[str, str]]]] = None
_DUMP = False


def read_rows(zip_path: Path, every: int = 1) -> Iterator[Item]:
    """Active domestic corporations: (corporate number, prefecture, municipality, street, code5, postal7)."""
    with zipfile.ZipFile(zip_path) as z:
        name = next(i.filename for i in z.infolist() if i.filename.endswith(".csv"))
        with z.open(name) as fh:
            for n, row in enumerate(csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline=""))):
                if len(row) < 24 or row[23] != "1" or row[18] or not (row[9] and row[10] and row[11]):
                    continue  # superseded record, closed corporation, or no domestic address
                if n % every:
                    continue
                yield row[1], row[9], row[10], row[11], row[13] + row[14], row[15]


def _postal_index() -> Dict[str, List[Tuple[str, str]]]:
    """Japan Post area codes: postal code -> [(municipality code, town key)]."""
    global _POSTAL_INDEX
    if _POSTAL_INDEX is None:
        index: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for line in common.ENGINE.gazetteer._postal().text.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 7 and parts[0].isdigit():
                index[parts[0]].append((parts[1], parts[2]))
        _POSTAL_INDEX = dict(index)
    return _POSTAL_INDEX


def _town_keys(c: Any) -> Set[str]:
    from jaden.core.townkey import town_key
    names = {c.town, c.oaza, c.koaza, (c.oaza or "") + (c.koaza or ""), (c.town or "") + (c.koaza or "")}
    return {town_key(n) for n in names if n}


def postal_outcome(res: Any, postal: str) -> str:
    """Whether the town JADEN resolved is one the row's postal code covers."""
    c = res.components
    areas = _postal_index().get(postal)
    if not areas:
        return "postal code is not an area code (business code or retired)"
    here = [key for lg, key in areas if lg == c.lg_code]
    if not here:
        return "postal code belongs to another municipality"
    if "" in here and len(here) == 1:
        return "municipality-wide postal code"
    if c.town_verified is not True:
        return "town not verified"
    mine = _town_keys(c)
    if any(key and (key in mine or any(m.startswith(key) or key.startswith(m) for m in mine)) for key in here):
        return "agree"
    return "disagree"


def _example(address: str, res: Any, val: Any, extra: str = "") -> Dict[str, Any]:
    return {"input": address, "canonical": res.canonical, "status": val.status,
            "message": val.message, "notes": list(res.notes)[:3], "extra": extra}


def score(batch: List[Item]) -> Tuple[Tally, Any]:
    tally = Tally()
    dump: List[Dict[str, Any]] = []
    for ident, pref, city, street, truth, postal in batch:
        full = pref + city + street
        res, val = resolve(full)
        outcome = municipality_outcome(res, val, truth)
        ex = None if outcome == "correct" else _example(full, res, val, truth)
        tally.add("full", outcome, ident, ex)
        if ex and _DUMP:
            dump.append({"test": "full", "outcome": outcome, **ex})
        if outcome == "correct":
            c = res.components
            town = ("town verified" if c.town_verified else
                    "town not in the registry" if c.town_verified is False else "no town written")
            ex = None if c.town_verified else _example(full, res, val)
            tally.add("town", town, ident, ex)
            if ex and _DUMP:
                dump.append({"test": "town", "outcome": town, **ex})
            tally.add("precision", res.precision)
            if len(postal) == 7:
                p = postal_outcome(res, postal)
                ex = _example(full, res, val, postal) if p in ("disagree", "postal code belongs to another municipality") else None
                tally.add("postal", p, ident, ex)
                if ex and _DUMP:
                    dump.append({"test": "postal", "outcome": p, **ex})

        short = city + street
        res, val = resolve(short)
        outcome = municipality_outcome(res, val, truth)
        ex = None if outcome == "correct" else _example(short, res, val, truth)
        tally.add("no prefecture", outcome, ident, ex)
        if ex and _DUMP and outcome != "ambiguous, truth listed":
            dump.append({"test": "no prefecture", "outcome": outcome, **ex})

        if len(postal) == 7:
            labelled = f"〒{postal[:3]}-{postal[3:]} {full}"
            res, val = resolve(labelled)
            outcome = municipality_outcome(res, val, truth)
            ex = None if outcome == "correct" else _example(labelled, res, val, truth)
            tally.add("with postal code", outcome, ident, ex)
            if ex and _DUMP:
                dump.append({"test": "with postal code", "outcome": outcome, **ex})
    return tally, dump


def main() -> int:
    global _DUMP
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="directory holding companies/zenkoku.zip")
    ap.add_argument("--every", type=int, default=1, help="use every Nth row (default: all)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--dump", type=Path, help="write every failure to this JSONL file (not for committing)")
    ap.add_argument("--out", type=Path, default=common.HERE / "results")
    args = ap.parse_args()
    _DUMP = args.dump is not None

    zip_path = args.data / "companies" / "zenkoku.zip"
    dump_fh = open(args.dump, "w", encoding="utf-8") if args.dump else None

    def on_extra(rows: List[Dict[str, Any]]) -> None:
        if dump_fh:
            for r in rows:
                dump_fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    tally, n, seconds = run_pool(score, read_rows(zip_path, args.every), args.jobs, on_extra=on_extra, label="companies: ")
    if dump_fh:
        dump_fh.close()

    provenance = {}
    prov_path = args.data / "companies" / "provenance.json"
    if prov_path.exists():
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))

    lines = ["# Real data: registered company addresses (National Tax Agency)", ""]
    lines.append(f"Source: 国税庁法人番号公表サイト, full download `{provenance.get('file', 'zenkoku.zip')}` "
                 f"(data as of {provenance.get('as_of', 'unknown')}). Rows used: active corporations with a domestic "
                 f"address{'' if args.every == 1 else f', every {args.every}th row'}: **{n:,}**. "
                 f"Processed in {seconds:,.0f} s ({3 * n / seconds:,.0f} addresses/s on {args.jobs} processes; "
                 "each row is resolved three ways).")
    lines += ["", "Every row is a real registered address, so the right outcome is always `correct`.", ""]
    for group, title in (("full", "Full address (prefecture + municipality + registered text)"),
                         ("no prefecture", "Without the prefecture"),
                         ("with postal code", "With the registered postal code in front")):
        lines += [f"## {title}", "", outcome_table(tally, group), ""]
    total_ok = tally.total("town")
    lines += ["## Town (of the addresses with the right municipality)", "", outcome_table(tally, "town"), ""]
    lines += ["## Town against the registered postal code", "",
              "The row's postal code is looked up in Japan Post's area codes; `agree` means the town JADEN "
              "resolved is one of the towns that code covers.", "", outcome_table(tally, "postal"), ""]
    agree, disagree = tally.get("postal", "agree"), tally.get("postal", "disagree")
    lines += [f"Where both sides name a town: **{pct(agree, agree + disagree)}** agree "
              f"({agree:,} of {agree + disagree:,}).", ""]
    lines += ["## Precision reached", "", outcome_table(tally, "precision"), ""]

    lines += ["## Examples of what is not `correct`", ""]
    for group in ("full", "no prefecture", "with postal code", "town", "postal"):
        for outcome in tally.group(group):
            shown = tally.sample(group, outcome, args.examples)
            if not shown:
                continue
            lines += [f"**{group}: {outcome}** ({tally.get(group, outcome):,})", ""]
            lines += [table(("Input", "JADEN", "Message"),
                            [(e["input"], f"{e['status']}: {e['canonical']}", (e["notes"][0] if e["notes"] else e["message"]))
                             for e in shown], "lll"), ""]

    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.every == 1 else f"_every{args.every}"
    (args.out / f"companies_report{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    scores = {"rows": n, "every": args.every, "seconds": round(seconds, 1), "provenance": provenance,
              "outcomes": {g: tally.group(g) for g in ("full", "no prefecture", "with postal code", "town", "postal", "precision")}}
    (args.out / f"companies_scores{suffix}.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines[:60]))
    print(f"\n(town checked on {total_ok:,} addresses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
