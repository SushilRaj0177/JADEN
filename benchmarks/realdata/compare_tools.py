"""Runs JADEN and other Japanese address tools on the same real addresses and scores them by one rule.

Step 1 writes the inputs (and JADEN's answers) as JSONL, one object per address:
    {"id", "set", "input", "truth"}         truth = the row's own five-digit municipality code
Step 2 runs the other tools on that file (benchmarks/jabench/baselines/), each writing
    {"id", "lg_code" | null, ...}
Step 3 scores every tool against the rows' own codes.

    python benchmarks/realdata/compare_tools.py inputs --out DIR [--care-every 1] [--companies-every 50]
    node benchmarks/jabench/baselines/geolonia_run.mjs DIR/inputs.jsonl DIR/geolonia_raw.jsonl 16 3
    python benchmarks/jabench/baselines/geolonia_to_jsonl.py DIR/geolonia_raw.jsonl DIR/geolonia.jsonl
    python benchmarks/jabench/baselines/jageocoder_run.py DIR/inputs.jsonl DIR/jageocoder.jsonl 4
    python benchmarks/realdata/compare_tools.py score --dir DIR --external geolonia=DIR/geolonia.jsonl jageocoder=DIR/jageocoder.jsonl

Every tool is scored the same way. A tool ANSWERS when it commits to one municipality; JADEN's
ambiguous results and rejections, and the other tools' results without a municipality, are NO ANSWER.
An answer is right when it names the row's municipality (or a ward of the row's designated city),
"city only" when it names the designated city of the row's ward, and wrong otherwise. Rows whose
code no longer exists are left out for every tool.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import common
from common import DEFAULT_DATA, pct, run_pool, table

SETS = {
    "care: as typed": "Care offices, as typed",
    "care: with columns": "Care offices, with the row's prefecture and municipality",
    "companies: full": "Companies, registered address",
    "companies: no prefecture": "Companies, without the prefecture",
    "companies: postal code in front": "Companies, postal code in front",
}


def build_inputs(data: Path, care_every: int, companies_every: int) -> Iterator[Dict[str, str]]:
    import evaluate_care
    import evaluate_companies
    for ident, pref, city, address, _k, truth, _la, _lo, _o in evaluate_care.read_rows(data / "care", care_every):
        yield {"id": f"c:{ident}:t", "set": "care: as typed", "input": address, "truth": truth[:5]}
        yield {"id": f"c:{ident}:c", "set": "care: with columns",
               "input": evaluate_care.compose(pref, city, address), "truth": truth[:5]}
    zips = sorted((data / "companies").glob("*.zip"))
    for ident, pref, city, street, truth, postal in evaluate_companies.read_rows(zips[-1], companies_every):
        yield {"id": f"n:{ident}:f", "set": "companies: full", "input": pref + city + street, "truth": truth}
        yield {"id": f"n:{ident}:s", "set": "companies: no prefecture", "input": city + street, "truth": truth}
        if len(postal) == 7:
            yield {"id": f"n:{ident}:p", "set": "companies: postal code in front",
                   "input": f"〒{postal[:3]}-{postal[3:]} {pref}{city}{street}", "truth": truth}


def jaden_batch(batch: List[Dict[str, str]]) -> Tuple[common.Tally, Any]:
    out = []
    for item in batch:
        res, val = common.resolve(item["input"])
        lg = res.components.lg_code if val.status == "ACCEPTED" else None
        listed = val.status == "AMBIGUOUS" and any(f"({item['truth']}" in c for c in val.ambiguous_candidates)
        out.append({"id": item["id"], "lg_code": lg, "status": val.status, "truth_listed": listed})
    return common.Tally(), out


def cmd_inputs(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    items = list(build_inputs(args.data, args.care_every, args.companies_every))
    with open(args.out / "inputs.jsonl", "w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"{len(items):,} inputs", Counter(i["set"] for i in items))
    with open(args.out / "jaden.jsonl", "w", encoding="utf-8") as fh:
        def on_extra(rows: List[Dict[str, Any]]) -> None:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        _, n, seconds = run_pool(jaden_batch, items, args.jobs, on_extra=on_extra, label="jaden: ")
    (args.out / "jaden_seconds.json").write_text(json.dumps({"seconds": seconds, "inputs": n}))
    return 0


def outcome(lg: Optional[str], truth5: str, known: Dict[str, Any]) -> str:
    if not lg:
        return "no answer"
    if lg[:5] == truth5:
        return "right"
    truth, mine = known.get(truth5), known.get(lg[:5])
    if mine is not None and mine.city == truth.city and mine.prefecture_code == truth.prefecture_code:
        if truth.entity_type == "designated_city" and mine.ward:
            return "right"
        if mine.entity_type == "designated_city" and truth.ward:
            return "city only"
    return "wrong"


def load(path: Path) -> Dict[str, Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return {r["id"]: r for r in map(json.loads, fh) if r}


def cmd_score(args: argparse.Namespace) -> int:
    known = common._municipalities()
    items = [json.loads(line) for line in open(args.dir / "inputs.jsonl", encoding="utf-8")]
    systems = {"JADEN": load(args.dir / "jaden.jsonl")}
    for spec in args.external:
        name, _, path = spec.partition("=")
        systems[name] = load(Path(path))

    counts: Dict[str, Dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    examples: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    left_out = Counter()
    missing = Counter()
    for item in items:
        if item["truth"] not in known:
            left_out[item["set"]] += 1
            continue
        answers = {name: ((results.get(item["id"]) or {}).get("lg_code") or "")[:5] for name, results in systems.items()}
        for name, results in systems.items():
            r = results.get(item["id"])
            if r is None:
                missing[name] += 1
                o = "no answer"
            else:
                o = outcome(r.get("lg_code"), item["truth"], known)
            counts[item["set"]][name][o] += 1
            shared = o == "wrong" and len(set(answers.values())) == 1
            if shared:
                # Every tool reads the text as the same other municipality: most likely the row is wrong
                counts[item["set"]][name]["wrong: every tool gives the same answer"] += 1
            if o == "wrong" and r["lg_code"][:5] not in known:
                counts[item["set"]][name]["wrong: a municipality code that no longer exists"] += 1
            if name == "JADEN" and r and o == "no answer" and r.get("truth_listed"):
                counts[item["set"]][name]["no answer: candidate list holds the truth"] += 1
            if o in ("wrong", "city only") and not shared and len(examples[(item["set"], name)]) < 400:
                m = known.get(r["lg_code"][:5]) if r and r.get("lg_code") else None  # type: ignore[index]
                t = known[item["truth"]]
                examples[(item["set"], name)].append(
                    f"`{item['input']}` → {m.prefecture_name + m.name if m else r['lg_code']} (row: {t.prefecture_name + t.name})")

    names = list(systems)
    scores: Dict[str, Any] = {"sets": {}, "left_out": dict(left_out), "missing": dict(missing)}
    lines = ["# Comparison with other tools on real addresses", ""]
    lines.append("Every tool gets the same text and is scored by the same rule (see `compare_tools.py`). "
                 "**Right**: names the row's own municipality. **Wrong**: names another one. **No answer**: "
                 "returns no single municipality (JADEN: ambiguous or rejected). **Precision**: right / answered.")
    lines.append("")
    rows = []
    for key, label in SETS.items():
        if key not in counts:
            continue
        scores["sets"][key] = {}
        for name in names:
            c = counts[key][name]
            total = c["right"] + c["wrong"] + c["city only"] + c["no answer"]
            answered = total - c["no answer"]
            scores["sets"][key][name] = dict(c)
            own = c["wrong"] - c["wrong: every tool gives the same answer"]
            rows.append([label, name, f"{total:,}", f"**{pct(c['right'], total)}**", f"{c['wrong']:,} ({pct(c['wrong'], total)})",
                         f"**{own:,}**", f"{c['city only']:,}", f"{c['no answer']:,} ({pct(c['no answer'], total)})",
                         pct(c["right"], answered)])
            label = ""
    lines.append(table(["Input", "Tool", "Addresses", "Right", "Wrong", "Wrong, tools disagree", "City, not ward",
                        "No answer", "Precision"], rows, "llrrrrrrr"))
    lines.append("")
    lines.append("**Wrong, tools disagree** leaves out the wrong answers that every tool shares: when all of them read "
                 "the text as the same other municipality, the row's own code is most likely what is wrong (for "
                 "example `北海道網走郡美幌町…` filed under 網走市). The examples below leave them out too.")
    lines.append("")
    jaden_listed = {k: counts[k]["JADEN"]["no answer: candidate list holds the truth"] for k in counts}
    lines.append("JADEN's \"no answer\" includes its ambiguous results, where it returns the possible municipalities "
                 "instead of one; the row's municipality is in that list for " +
                 ", ".join(f"{n:,} ({SETS[k].lower()})" for k, n in jaden_listed.items() if n) + ".")
    for name in names:
        retired = sum(counts[k][name]["wrong: a municipality code that no longer exists"] for k in counts)
        if retired:
            lines.append("")
            lines.append(f"{retired:,} of {name}'s wrong answers name a municipality that no longer exists "
                         "(for example 浜松市中区, abolished in 2024): it read an old address under its old name.")
    if any(left_out.values()):
        lines.append("")
        lines.append(f"Left out for every tool: {sum(left_out.values()):,} inputs whose row carries a municipality code "
                     "that no longer exists.")
    lines.append("")
    lines.append("## Examples of wrong answers (and of a designated city named without its ward)")
    for key, label in SETS.items():
        for name in names:
            ex = examples.get((key, name), [])
            if ex:
                lines.append("")
                lines.append(f"**{label}, {name}** ({min(len(ex), args.examples)} of {len(ex):,}"
                             f"{'+' if len(ex) == 400 else ''}, spread over the data)")
                lines.append("")
                step = max(1, len(ex) // args.examples)
                lines += [f"- {e}" for e in ex[::step][: args.examples]]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "comparison_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.out / "comparison_scores.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1) + "\n",
                                                      encoding="utf-8")
    print("\n".join(lines[:40]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("inputs")
    a.add_argument("--data", type=Path, default=DEFAULT_DATA)
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--care-every", type=int, default=1)
    a.add_argument("--companies-every", type=int, default=50)
    a.add_argument("--jobs", type=int, default=4)
    s = sub.add_parser("score")
    s.add_argument("--dir", type=Path, required=True)
    s.add_argument("--external", nargs="*", default=[])
    s.add_argument("--examples", type=int, default=8)
    s.add_argument("--out", type=Path, default=common.HERE / "results")
    args = ap.parse_args()
    return cmd_inputs(args) if args.cmd == "inputs" else cmd_score(args)


if __name__ == "__main__":
    sys.exit(main())
