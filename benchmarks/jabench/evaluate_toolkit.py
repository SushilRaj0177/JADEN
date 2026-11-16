"""JA-AddrBench toolkit evaluation: the features built on top of address resolution.

Every test starts from the 4,700 real `original` addresses of jabench.jsonl (and the
34,032 noisy variants of reallife.jsonl) and derives its own ground truth from them:

  matching     every noisy spelling must get the match key of its clean address; distinct
               addresses must get distinct keys
  typos        one character of the town is replaced; the right address must be suggested,
               and autocorrect must never produce a different one
  kana         the town is rewritten in hiragana; the result must not change
  hyphen       the compact 4-2-8 form must normalize back to the same result
  extraction   the address is embedded in sentences, labels and parentheses; the span found
               must be exactly the address, and text without an address must give nothing
  suggest      typing the prefecture, municipality and first two characters of the town
               must offer the real town
  postal       the postal code JADEN fills in must look up to the same municipality
  reverse      the surveyed school point must reverse-geocode to the school's municipality
               (and town)

Usage:
    python benchmarks/jabench/evaluate_toolkit.py [--blocks-dir DIR] [--examples 3]
Writes results/toolkit_report.md and results/toolkit_scores.json.
"""

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

_TYPO_POOL = "山川田中村上下東西南北大小新本原野島崎木林森谷沢池橋岡"


def _load() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    originals = [json.loads(line) for line in open(HERE / "jabench.jsonl", encoding="utf-8")]
    originals = [it for it in originals if it["variant"] == "original"]
    reallife = [json.loads(line) for line in open(HERE / "reallife.jsonl", encoding="utf-8")]
    return originals, reallife


def _replace_last(text: str, old: str, new: str) -> str:
    """Replaces the last occurrence: the town, not a municipality of the same name before it."""
    i = text.rfind(old)
    return text[:i] + new + text[i + len(old):] if i >= 0 else text


def _hiragana(katakana: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in katakana)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks-dir", type=Path, help="blocks/NN.tsv.gz directory for block-level reverse geocoding")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    import jaden
    from jaden.core.townkey import town_key
    from jaden.data.gazetteer import Gazetteer, get_gazetteer
    from jaden.engine import AddressNormalizer
    from jaden.extract import extract_addresses
    from jaden.lookup import lookup_postal, reverse_geocode, suggest
    from jaden.matching import match_key

    originals, reallife = _load()
    rng = random.Random(11)
    gaz = get_gazetteer()
    scores: Dict[str, Any] = {}
    examples: Dict[str, List[Any]] = defaultdict(list)
    lines: List[str] = []
    base = {it["input"]: jaden.normalize(it["input"]) for it in originals}

    # ------------------------------------------------------------ matching
    t0 = time.perf_counter()
    base_keys = {a: match_key(r, "house") for a, r in base.items()}
    keyed = same = 0
    unit_keys: Dict[str, set] = defaultdict(set)
    for it in reallife:
        bk = base_keys.get(it["base"]) or match_key(it["base"], "house")
        if bk is None:
            continue
        keyed += 1
        res = jaden.normalize(it["input"])
        if match_key(res, "house") == bk:
            same += 1
        else:
            examples["matching"].append((it["input"], match_key(res, "house"), bk))
        if it["unit"]:
            unit_keys[it["base"]].add(match_key(res, "unit"))
    by_key: Dict[str, List[str]] = defaultdict(list)
    for a, k in base_keys.items():
        if k:
            by_key[k].append(a)
    shared = [v for v in by_key.values() if len(v) > 1]
    scores["matching"] = {
        "variants_with_key": keyed, "variants_same_key_as_clean": same,
        "bases_with_inconsistent_room_keys": sum(1 for v in unit_keys.values() if len(v) > 1),
        "distinct_addresses_keyed": sum(1 for k in base_keys.values() if k),
        "key_shared_by_distinct_addresses": len(shared), "shared_groups": shared,
        "seconds": round(time.perf_counter() - t0, 1),
    }

    # --------------------------------------------------------------- typos
    fixer = AddressNormalizer(autocorrect=True)
    typo = Counter()
    for it in originals:
        res = base[it["input"]]
        c = res.components
        town = c.town or ""
        if not (c.town_verified and c.lg_code and town in it["input"] and len(town_key(town)) >= 3):
            continue
        pos = rng.randrange(len(town))
        if town[pos].isdigit():
            continue
        wrong = rng.choice([ch for ch in _TYPO_POOL if ch != town[pos]])
        typo_town = town[:pos] + wrong + town[pos + 1:]
        # Skip typos that are real towns, or that the engine still reads as the same registered town
        if gaz.match_town(c.lg_code, typo_town) is not None:
            continue
        text = _replace_last(it["input"], town, typo_town)
        plain = jaden.normalize(text)
        if plain.components.town_verified is not False:
            continue
        typo["tested"] += 1
        truth = match_key(res, "town")
        if any(match_key(s, "town") == truth for s in plain.suggestions):
            typo["suggested"] += 1
        elif len(examples["typos"]) < 50:
            examples["typos"].append((text, res.canonical, plain.suggestions))
        fixed = fixer.normalize(text)
        if fixed.components.town_corrected_from is None:
            typo["autocorrect_left_alone"] += 1
        elif match_key(fixed, "town") == truth:
            typo["autocorrect_right"] += 1
        else:
            typo["autocorrect_wrong"] += 1
            examples["autocorrect_wrong"].append((text, fixed.canonical, res.canonical))
    scores["typos"] = dict(typo)

    # ---------------------------------------------------------------- kana
    kana = Counter()
    for it in originals:
        res = base[it["input"]]
        c = res.components
        town = c.town or ""
        match = gaz.match_town(c.lg_code, town) if (c.lg_code and c.town_verified) else None
        if match is None or not match.exact or not match.entry.kana or town not in it["input"]:
            continue
        if any(ch.isdigit() for ch in match.entry.kana) or c.hokkaido_grid is not None:
            continue
        text = _replace_last(it["input"], town, _hiragana(match.entry.kana))
        kana["tested"] += 1
        got = jaden.normalize(text)
        if got.components.town_verified and match_key(got, "unit") == match_key(res, "unit"):
            kana["same_result"] += 1
        elif got.components.town_verified is False:
            kana["not_resolved"] += 1
            examples["kana"].append((text, got.canonical, res.canonical))
        else:
            kana["different_result"] += 1
            examples["kana_wrong"].append((text, got.canonical, res.canonical))
    scores["kana"] = dict(kana)

    # -------------------------------------------------------------- hyphen
    bad = [a for a, r in base.items() if jaden.normalize(r.format("hyphen")).canonical != r.canonical]
    scores["hyphen_round_trip"] = {"tested": len(base), "same_result": len(base) - len(bad)}
    examples["hyphen"] = bad

    # ---------------------------------------------------------- extraction
    templates = {
        "sentence": "会場は{a}にあります。お問い合わせは03-1234-5678まで。",
        "label": "名称: {n}\n住所: {a}\nTEL: 03-1234-5678\n営業時間: 10:00-19:00",
        "parentheses": "{n}（{a}）",
        "postal": "〒{p} {a}　TEL 03-1234-5678",
        "with_room": "お届け先は{a} メゾン桜 302号室 です。よろしくお願いします。",
    }
    ext: Dict[str, Counter] = {name: Counter() for name in templates}
    ext["no_address"] = Counter()
    schools = {it["input"]: it for it in originals}
    names = {}
    for line in open(HERE / "jabench.jsonl", encoding="utf-8"):
        row = json.loads(line)
        if row["variant"] == "non_address":
            names[(row["source_lg"], row["lat"], row["lon"])] = row["input"]
    for a, it in schools.items():
        res = base[a]
        name = names.get((it["source_lg"], it["lat"], it["lon"]), "本校")
        for tname, template in templates.items():
            if tname == "postal" and not res.components.postal_code:
                continue
            expected = a if tname != "postal" else f"〒{res.components.postal_code} {a}"
            if tname == "with_room":
                expected = f"{a} メゾン桜 302号室"
            text = template.format(a=a, n=name, p=res.components.postal_code)
            found = extract_addresses(text)
            ext[tname]["tested"] += 1
            right_place = [x for x in found if x.lg_code == it["gold_lg"]]
            if right_place:
                ext[tname]["found"] += 1
            if len(found) == 1 and found[0].text == expected:
                ext[tname]["exact_span"] += 1
            elif len(examples[f"extract_{tname}"]) < 40:
                examples[f"extract_{tname}"].append((text, [x.text for x in found]))
            if len(found) > 1:
                ext[tname]["extra_spans"] += len(found) - 1
        noise = f"{name}は2024年4月1日に開校しました。電話 03-1234-5678、定員120名、参加費3,000円。"
        ext["no_address"]["tested"] += 1
        got = extract_addresses(noise)
        if got:
            ext["no_address"]["false_positive"] += 1
            if len(examples["extract_false_positive"]) < 40:
                examples["extract_false_positive"].append((noise, [x.text for x in got]))
    scores["extraction"] = {k: dict(v) for k, v in ext.items()}

    # ------------------------------------------------------------- suggest
    sug = Counter()
    for a, res in base.items():
        c = res.components
        town = c.town or ""
        match = gaz.match_town(c.lg_code, town) if (c.lg_code and c.town_verified) else None
        if match is None or c.hokkaido_grid is not None or len(match.entry.name.lstrip("大字")) < 3:
            continue
        muni = jaden.get_registry().get_municipality_by_code(c.lg_code)
        if muni is None:
            continue
        name = match.entry.name[2:] if match.entry.name.startswith("大字") else match.entry.name.lstrip("字")
        head = f"{muni.prefecture_name}{(muni.county or '') + muni.name}"
        target = head + match.entry.name
        sug["tested"] += 1
        for n in (2, 3):
            offered = [s.text for s in suggest(head + name[:n], limit=10)]
            if target in offered:
                sug[f"after_{n}_chars"] += 1
            elif n == 3 and len(examples["suggest"]) < 40:
                examples["suggest"].append((head + name[:n], target, offered[:5]))
    scores["suggest"] = dict(sug)

    # -------------------------------------------------------------- postal
    post = Counter()
    for a, res in base.items():
        code = res.components.postal_code
        if not code:
            continue
        post["tested"] += 1
        if any(p.lg_code == res.components.lg_code for p in lookup_postal(code)):
            post["same_municipality"] += 1
    scores["postal"] = dict(post)

    # ------------------------------------------------------------- reverse
    def reverse_scores(label: str) -> None:
        rv = Counter()
        dists = []
        for a, it in schools.items():
            hits = reverse_geocode(it["lat"], it["lon"])
            rv["tested"] += 1
            if not hits:
                continue
            hit = hits[0]
            dists.append(hit.distance_m)
            if hit.lg_code == it["gold_lg"]:
                rv["municipality"] += 1
            c = base[a].components
            if c.town_verified and c.hokkaido_grid is None:
                rv["town_tested"] += 1
                if hit.lg_code == c.lg_code and town_key(c.town or "").startswith(town_key(hit.town)):
                    rv["town"] += 1
                    if c.chome is not None:
                        rv["chome_tested"] += 1
                        rv["chome"] += int(hit.chome == c.chome)
        dists.sort()
        scores[label] = {**dict(rv), "median_distance_m": dists[len(dists) // 2] if dists else None}

    reverse_scores("reverse_town_points")
    if args.blocks_dir:
        import jaden.data.gazetteer as gmod
        with_blocks = Gazetteer()
        with_blocks.block_dirs = lambda: [args.blocks_dir]  # type: ignore[method-assign]
        gmod._GAZETTEER = with_blocks
        reverse_scores("reverse_with_blocks")
        gmod._GAZETTEER = gaz

    # -------------------------------------------------------------- report
    def pct(n: int, d: int) -> str:
        return f"{n:,} / {d:,} ({100 * n / d:.1f}%)" if d else "–"

    m = scores["matching"]
    lines += ["## Matching (名寄せ)", "",
              f"* Noisy spellings that get the same key as their clean address: {pct(m['variants_same_key_as_clean'], m['variants_with_key'])}",
              f"* Addresses whose room is written four ways but keyed differently: {m['bases_with_inconsistent_room_keys']}",
              f"* Distinct published addresses sharing a key: {m['key_shared_by_distinct_addresses']} pairs of "
              f"{m['distinct_addresses_keyed']:,} (listed in toolkit_scores.json; each is one place written two ways)", ""]
    t = scores["typos"]
    lines += ["## Typos (one character of the town replaced)", "",
              f"* Correct address offered in `suggestions`: {pct(t.get('suggested', 0), t['tested'])}",
              f"* Autocorrect applied and right: {pct(t.get('autocorrect_right', 0), t['tested'])}",
              f"* Autocorrect applied and wrong: {t.get('autocorrect_wrong', 0)}",
              f"* Left uncorrected (more than one candidate, or none): {t.get('autocorrect_left_alone', 0):,}", ""]
    k = scores["kana"]
    lines += ["## Town written in hiragana", "",
              f"* Same result as the kanji spelling: {pct(k.get('same_result', 0), k['tested'])}",
              f"* Not resolved (two towns share the reading, or no reading on file): {k.get('not_resolved', 0)}",
              f"* Resolved to a different town: {k.get('different_result', 0)}", ""]
    h = scores["hyphen_round_trip"]
    lines += ["## Hyphen form round trip", "", f"* Same result after normalizing the 4-2-8 form: {pct(h['same_result'], h['tested'])}", ""]
    lines += ["## Extraction from text", "", "| Context | Tested | Address found | Exact span | Extra spans |", "|---|---:|---:|---:|---:|"]
    for name in templates:
        e = scores["extraction"][name]
        lines.append(f"| {name} | {e['tested']:,} | {100 * e.get('found', 0) / e['tested']:.1f}% | "
                     f"{100 * e.get('exact_span', 0) / e['tested']:.1f}% | {e.get('extra_spans', 0)} |")
    n = scores["extraction"]["no_address"]
    lines += ["", f"* Text with a school name, date, phone number and price but no address: "
                  f"{n.get('false_positive', 0)} false positives in {n['tested']:,}", ""]
    s = scores["suggest"]
    lines += ["## Autocomplete (real town among the first 10 suggestions)", "",
              f"* After typing the municipality and 2 characters of the town: {pct(s.get('after_2_chars', 0), s['tested'])}",
              f"* After 3 characters: {pct(s.get('after_3_chars', 0), s['tested'])}", ""]
    p = scores["postal"]
    lines += ["## Postal lookup", "", f"* Filled-in postal code looks up to the same municipality: {pct(p.get('same_municipality', 0), p['tested'])}", ""]
    lines += ["## Reverse geocoding (surveyed school point -> address)", "",
              "| Data | Municipality | Town | 丁目 (when town right) | Median distance to matched point |", "|---|---:|---:|---:|---:|"]
    for label, title in (("reverse_town_points", "bundled town points"), ("reverse_with_blocks", "+ block data")):
        if label in scores:
            r = scores[label]
            lines.append(f"| {title} | {100 * r['municipality'] / r['tested']:.1f}% | {100 * r['town'] / r['town_tested']:.1f}% | "
                         f"{100 * r['chome'] / r['chome_tested']:.1f}% | {r['median_distance_m']:.0f} m |")
    report = "\n".join(lines) + "\n"
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "toolkit_report.md").write_text(report, encoding="utf-8")
    with open(out / "toolkit_scores.json", "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    print(report)
    for name, items in examples.items():
        if items and args.examples:
            print(f"-- {name}: {len(items)} cases")
            for item in items[:args.examples]:
                print("   ", item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
