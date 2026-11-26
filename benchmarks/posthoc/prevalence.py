"""Post-hoc: how often real hand-typed addresses leave out the prefecture or the municipality.

The care-office register gives, for every office, the address as typed by the office and, in separate
columns, its prefecture and municipality. An address "writes" the prefecture when it starts with it
(with or without 都/道/府/県), and the municipality when its name (without the county) appears near the
start. This is a text check, so it is approximate: a municipality written in a different form counts as
left out.

Usage:
    python benchmarks/posthoc/prevalence.py [--data ~/.cache/jaden-realdata]
"""

import argparse
import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path.home() / ".cache" / "jaden-realdata")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    args = ap.parse_args()
    c: Counter = Counter()
    for path in sorted((args.data / "care").glob("jigyosho_*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            for row in reader:
                if len(row) < 16 or not row[7].strip():
                    continue
                address = unicodedata.normalize("NFKC", row[7]).strip()
                pref, city = row[2], row[3]
                c["addresses"] += 1
                has_pref = address.startswith(pref) or address.startswith(pref[:-1])
                name = city.split("郡", 1)[-1]
                head = address[:len(pref) + len(city) + 6]
                has_city = name in head or ("市" in city[:-1] and city.split("市", 1)[0] + "市" in head)
                c["prefecture left out"] += not has_pref
                c["municipality left out"] += not has_city
                c["both left out"] += not has_pref and not has_city
    n = c["addresses"]
    lines = ["# Post-hoc: how often hand-typed addresses leave out the prefecture or municipality", "",
             f"MHLW care-office register, addresses as typed by the offices: {n:,}.", "",
             "| Left out | Addresses | Share |", "| :--- | ---: | ---: |"]
    for k in ("prefecture left out", "municipality left out", "both left out"):
        lines.append(f"| {k} | {c[k]:,} | {100 * c[k] / n:.1f}% |")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "prevalence.json").write_text(json.dumps(dict(c), ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "prevalence.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
