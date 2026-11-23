"""Real-data evaluation on the addresses of every long-term-care office in Japan.

Source: Ministry of Health, Labour and Welfare, 介護サービス情報公表システム open data (35 CSV files,
one per service). Offices type their own address, so the spelling is whatever people write:
with or without the prefecture or municipality, full-width or kanji numbers, the building glued
to the house number. Each row also carries, independently of that text:

  the municipality code      -> is JADEN's municipality right?
  方書 (building, floor, room) -> does JADEN cut the address from the building at the same place?
  latitude / longitude        -> how far is JADEN's offline point from the published one?
  事業所番号 (office number)    -> the same office listed under several services, sometimes with the
                                 address typed differently: do they get the same match key?

Usage:
    python benchmarks/realdata/download.py care
    python benchmarks/realdata/evaluate_care.py [--every 10] [--jobs 4] [--dump failures.jsonl]
"""

import argparse
import csv
import re
import json
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import common
from common import (DEFAULT_DATA, Tally, fold, haversine_km, is_correct, municipality_outcome, outcome_table, pct,
                    resolve, run_pool, table)

# (row id, prefecture, municipality, address as typed, 方書, municipality code, lat, lon, office number)
Item = Tuple[str, str, str, str, str, str, str, str, str]
_DUMP = False


def read_rows(folder: Path, every: int = 1) -> Iterator[Item]:
    n = 0
    for path in sorted(folder.glob("jigyosho_*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            next(reader)
            for row in reader:
                if len(row) < 16 or not row[7].strip():
                    continue
                n += 1
                if n % every:
                    continue
                yield (f"{path.stem}:{row[1]}", row[2], row[3], row[7], row[8].strip(), row[0], row[9], row[10], row[15])


def compose(pref: str, city: str, address: str) -> str:
    """The address a system would build from the three columns: nothing is repeated, nothing is dropped.

    The typed text keeps its own head when it already names the municipality somewhere near its start
    ('東京目黒区…', '下京区西七条…', '厚岸郡厚岸町…'); otherwise the columns are put in front.
    """
    a = address.strip()
    if a.startswith(pref):
        return a
    folded = fold(a)
    parts = [city]
    if "市" in city[:-1]:
        head, _, ward = city.partition("市")
        parts += [head + "市", ward]                 # '京都市下京区' -> '京都市', '下京区'
    if "郡" in city:
        parts.append(city.split("郡", 1)[1])
    for part in parts:
        if not part:
            continue
        where = folded.find(fold(part))
        if where == 0:
            return pref + a
        if 0 < where <= 4:
            return a                                   # its own (misspelt) prefecture in front
    county_free = a.split("郡", 1)[1] if "郡" in a[:6] else ""
    if city and county_free.startswith(city):
        return pref + a
    return pref + city + a


def _row_check(outcome: str, res: Any, address: str, city: str) -> str:
    """A row whose typed address names one municipality while its columns name another cannot be scored."""
    if outcome != "wrong":
        return outcome
    typed = fold(address)
    c = res.components
    mine = fold((c.city or "") + (c.ward or "") if c.ward and c.city != c.ward else (c.city or c.ward or ""))
    column = fold(city.split("郡")[-1])
    if mine and mine in typed and column and column not in typed.replace(mine, ""):
        return "not scored: the typed address and the row's columns name different municipalities"
    return outcome


def _address_part(res: Any) -> Tuple[Any, ...]:
    c = res.components
    return (c.lg_code, c.oaza, c.koaza, c.town, c.chome, c.ban, c.go, c.banchi, c.edaban, c.lot_number)


def _squash(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text or "").split())


def _example(address: str, res: Any, val: Any, extra: str = "") -> Dict[str, Any]:
    return {"input": address, "canonical": res.canonical, "status": val.status,
            "message": val.message, "notes": list(res.notes)[:3], "extra": extra}


def score(batch: List[Item]) -> Tuple[Tally, Any]:
    tally = Tally()
    dump: List[Dict[str, Any]] = []
    keys: List[Tuple[str, str, str]] = []
    distances: Dict[str, List[float]] = defaultdict(list)

    def note(test: str, outcome: str, ident: str, ex: Any) -> None:
        tally.add(test, outcome, ident, ex)
        if ex and _DUMP:
            dump.append({"test": test, "outcome": outcome, **ex})

    for ident, pref, city, address, katagaki, truth, lat, lon, office in batch:
        truth5 = truth[:5]
        res, val = resolve(address)
        outcome = _row_check(municipality_outcome(res, val, truth5), res, address, city)
        note("as typed", outcome, ident, None if is_correct(outcome) else _example(address, res, val, truth))

        composed = compose(pref, city, address)
        if composed != address:
            res, val = resolve(composed)
        outcome = _row_check(municipality_outcome(res, val, truth5), res, address, city)
        note("with the prefecture and municipality columns", outcome, ident,
             None if is_correct(outcome) else _example(composed, res, val, truth))
        if not is_correct(outcome):
            keys.append((office, address, ""))
            continue
        c = res.components
        town = ("town verified" if c.town_verified else
                "town not in the registry" if c.town_verified is False else "no town written")
        note("town", town, ident, None if c.town_verified else _example(composed, res, val))
        tally.add("precision", res.precision)

        # Distance to the published point
        try:
            there = (float(lat), float(lon))
        except ValueError:
            there = None
        if there and res.latitude is not None and 20 < there[0] < 50 and 120 < there[1] < 155:
            km = haversine_km(res.latitude, res.longitude, there[0], there[1])
            distances[res.location_level or "?"].append(km)
            if km > 20:
                note("location", "more than 20 km from the published point", ident,
                     _example(composed, res, val, f"{km:.0f} km; published {lat[:9]},{lon[:10]}"))

        # The building: cutting 方書 off the typed address must leave the same address
        if katagaki and composed.rstrip().endswith(katagaki) and len(composed.rstrip()) > len(katagaki):
            bare = composed.rstrip()[: -len(katagaki)].rstrip()
            base, _ = resolve(bare)
            b = base.components
            if b.building or b.unit or b.floor:
                tally.add("building", "not scored: the 方書 column holds only part of the building text")
            elif b.precision in ("municipality", "town", "chome") and not b.numbers_unplaced:
                tally.add("building", "not scored: the 方書 column holds the house number too")
            elif _address_part(base) == _address_part(res):
                mine = _squash(" ".join(x for x in (c.building, c.floor, c.unit) if x))
                tally.add("building", "same address, building separated" if mine else "same address, building text dropped")
            elif bare[-1:].isdigit() and unicodedata.normalize("NFKC", katagaki[:1]).isdigit():
                # '…2-31-2' + '101' published as '…2-31-2101': the text no longer says where the address ends
                note("building", "not decidable: the publisher glued a number to the house number", ident,
                     _example(composed, res, val, f"without the building: {base.canonical}"))
            else:
                note("building", "address changes when the building is attached", ident,
                     _example(composed, res, val, f"without the building: {base.canonical}"))

        from jaden.matching import match_key
        keys.append((office, address, match_key(composed, level="house") or ""))
    return tally, (dump, keys, dict(distances))


def main() -> int:
    global _DUMP
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="directory holding care/jigyosho_*.csv")
    ap.add_argument("--every", type=int, default=1, help="use every Nth row (default: all)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--dump", type=Path, help="write every failure to this JSONL file (not for committing)")
    ap.add_argument("--out", type=Path, default=common.HERE / "results")
    args = ap.parse_args()
    _DUMP = args.dump is not None

    dump_fh = open(args.dump, "w", encoding="utf-8") if args.dump else None
    by_office: Dict[str, Dict[str, str]] = defaultdict(dict)
    distances: Dict[str, List[float]] = defaultdict(list)

    def on_extra(extra: Any) -> None:
        dump, keys, dist = extra
        if dump_fh:
            for r in dump:
                dump_fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        for office, address, key in keys:
            by_office[office][address] = key
        for level, values in dist.items():
            distances[level].extend(values)

    tally, n, seconds = run_pool(score, read_rows(args.data / "care", args.every), args.jobs, on_extra=on_extra, label="care: ")

    # The same office typed in different ways: do the spellings share a house-level match key?
    from jaden.core.kanji_numerals import normalize_kanji_numerals_in_blocks
    office_examples: List[Tuple[str, str, str, str]] = []
    for office, spellings in sorted(by_office.items()):
        if len(spellings) < 2:
            continue
        keys = set(spellings.values())
        numbers = {tuple(re.findall(r"\d+", normalize_kanji_numerals_in_blocks(fold(a)))[:3]) for a in spellings}
        if len(numbers) > 1:
            outcome = "not scored: the spellings carry different numbers (a move, or a typo in the data)"
        elif "" in keys:
            outcome = "a spelling could not be keyed"
        elif len(keys) == 1:
            outcome = "all spellings share one key"
        else:
            outcome = "spellings get different keys"
            if len(office_examples) < 400:
                pair = sorted(spellings.items())[:2]
                office_examples.append((pair[0][0], pair[1][0], pair[0][1], pair[1][1]))
        tally.add("same office", outcome)
        if dump_fh and outcome != "all spellings share one key":
            dump_fh.write(json.dumps({"test": "same office", "outcome": outcome, "office": office,
                                      "spellings": spellings}, ensure_ascii=False) + "\n")
    if dump_fh:
        dump_fh.close()

    provenance = {}
    prov_path = args.data / "care" / "provenance.json"
    if prov_path.exists():
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))

    lines = ["# Real data: long-term-care office addresses (Ministry of Health, Labour and Welfare)", ""]
    lines.append(f"Source: 介護サービス情報公表システム オープンデータ (data as of {provenance.get('as_of', 'unknown')}, CC BY). "
                 f"Rows used: every office row with an address{'' if args.every == 1 else f', every {args.every}th row'}: "
                 f"**{n:,}**. Processed in {seconds:,.0f} s on {args.jobs} processes.")
    lines += ["", "Every row is a real office, so the right municipality outcome is always `correct`.", ""]
    for group, title in (("as typed", "The address exactly as typed (often without prefecture or municipality)"),
                         ("with the prefecture and municipality columns",
                          "With the row's prefecture and municipality columns put in front where the text lacks them")):
        lines += [f"## {title}", "", outcome_table(tally, group), ""]
    lines += ["## Town (of the addresses with the right municipality)", "", outcome_table(tally, "town"), ""]
    lines += ["## Building, floor and room against the 方書 column", "",
              "Rows whose typed address ends with the text of the 方書 column. The address is resolved with and "
              "without that text; the address part must not change.", "", outcome_table(tally, "building"), ""]
    shared = tally.get("same office", "all spellings share one key")
    scored = sum(n for o, n in tally.group("same office").items() if not o.startswith("not scored"))
    lines += ["## The same office listed several times with different spellings", "",
              "Offices (by 事業所番号) whose rows carry two or more different address strings. Where the strings "
              "carry the same numbers, they should get the same house-level match key.", "",
              outcome_table(tally, "same office"), "",
              f"Of the offices whose spellings carry the same numbers, **{pct(shared, scored)}** get one key "
              f"({shared:,} of {scored:,}).", ""]
    lines += ["## Distance from JADEN's offline point to the published coordinates", "",
              "The published coordinates come from the publishing system's own geocoding, so this is agreement "
              "between two systems, not error against a survey.", ""]
    rows = []
    for level, values in sorted(distances.items(), key=lambda kv: -len(kv[1])):
        values.sort()
        rows.append((level, f"{len(values):,}", f"{statistics.median(values) * 1000:,.0f} m",
                     pct(sum(v <= 1 for v in values), len(values), 1), pct(sum(v > 20 for v in values), len(values), 2)))
    lines += [table(("JADEN point level", "Addresses", "Median distance", "Within 1 km", "Over 20 km"), rows), ""]
    lines += ["## Precision reached", "", outcome_table(tally, "precision"), ""]

    lines += ["## Examples of what is not `correct`", ""]
    for group in ("as typed", "with the prefecture and municipality columns", "town", "building", "location"):
        if group == "building":
            lines += ["`not decidable` rows are shown for completeness; nothing in the text says where the number ends.", ""]
        for outcome in tally.group(group):
            shown = tally.sample(group, outcome, args.examples)
            if not shown:
                continue
            lines += [f"**{group}: {outcome}** ({tally.get(group, outcome):,})", ""]
            lines += [table(("Input", "JADEN", "Message"),
                            [(e["input"], f"{e['status']}: {e['canonical']}",
                              (e["extra"] if group in ("building", "location") else (e["notes"][0] if e["notes"] else e["message"])))
                             for e in shown], "lll"), ""]
    if office_examples:
        lines += ["**same office: spellings get different keys** (first examples)", "",
                  table(("Spelling A", "Spelling B", "Key A", "Key B"), office_examples[:args.examples], "llll"), ""]

    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "" if args.every == 1 else f"_every{args.every}"
    (args.out / f"care_report{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    groups = ("as typed", "with the prefecture and municipality columns", "town", "building", "same office", "precision", "location")
    scores = {"rows": n, "every": args.every, "seconds": round(seconds, 1), "provenance": provenance,
              "outcomes": {g: tally.group(g) for g in groups},
              "distance_km_median": {lvl: round(statistics.median(v), 4) for lvl, v in distances.items() if v}}
    (args.out / f"care_scores{suffix}.json").write_text(json.dumps(scores, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(lines[:80]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
