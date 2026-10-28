"""JA-AddrBench: builds an address-resolution benchmark from real, independently labelled addresses.

Source: 国土数値情報 学校データ (P29, 2023, MLIT), licensed CC BY 4.0
https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P29-2023.html

Every school record carries the address as published, the 行政区域コード of the
municipality it lies in (P29_001) and a surveyed point. The municipality code and
point come from the dataset itself, not from any of the systems being evaluated,
so they are an independent gold standard.

Variants built from each sampled address (gold label unchanged):
  original    the address as published
  no_pref     prefecture removed
  town_only   prefecture and municipality removed (the hardest: must be deduced or abstained)
  noisy       real-world formatting noise: full-width digits, other dash characters,
              kanji numerals with 丁目/番/号 markers, の delimiters, stray spaces
  romaji      the address in English order with Japan Post's official romanization
              ('3-2-1 Suehiro, Hirosaki-shi, Aomori'), where the town has one

Invalid variants (gold: must NOT be accepted as a valid address):
  wrong_pref      the prefecture replaced by another one (a contradiction)
  chome_99        the 丁目 replaced by 99 (no town in Japan has a 99丁目)
  non_address     the school name alone (often contains a municipality name)

Usage:
    python benchmarks/jabench/build_benchmark.py [--per-prefecture 100] [--seed 2026]
Writes benchmarks/jabench/jabench.jsonl and benchmarks/jabench/jabench_meta.json.
"""

import argparse
import hashlib
import io
import json
import random
import re
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

HERE = Path(__file__).parent
SRC_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/P29/P29-23/P29-23_{pref:02d}_GML.zip"
LANDING = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P29-2023.html"
ATTRIBUTION = "「国土数値情報（学校データ）」（国土交通省）（令和5年度）を加工して作成"

_KANJI_DIGITS = "〇一二三四五六七八九"


def _download(url: str, cache: Path) -> Tuple[bytes, str]:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / url.rsplit("/", 1)[-1]
    if not target.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "jabench-builder"})
        with urllib.request.urlopen(req, timeout=120) as r:
            target.write_bytes(r.read())
    data = target.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def _kanji_number(n: int) -> str:
    """Positional kanji numeral: 24 -> 二十四, 105 -> 百五."""
    if n == 0:
        return "〇"
    out = ""
    for value, unit in ((1000, "千"), (100, "百"), (10, "十")):
        q, n = divmod(n, value)
        if q:
            out += ("" if q == 1 else _KANJI_DIGITS[q]) + unit
    if n:
        out += _KANJI_DIGITS[n]
    return out


def _check_digit(d5: str) -> str:
    r = sum(int(d) * w for d, w in zip(d5, (6, 5, 4, 3, 2))) % 11
    return str((11 - r) % 10) if r <= 1 else str(11 - r)


POSTAL_URL = "https://www.post.japanpost.jp/service/search/zipcode/download/utf/zip/utf_ken_all.zip"


def _chome_towns(cache: Path) -> Tuple[Dict[str, List[str]], str]:
    """Towns that Japan Post flags as divided into 丁目 (KEN_ALL column 12), by municipality code.

    Used only to decide where a '99丁目' certainly does not exist; Japan Post is independent
    of the town list the evaluated systems use.
    """
    import csv
    data, digest = _download(POSTAL_URL, cache)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        text = zf.read(zf.namelist()[0]).decode("utf-8")
    towns: Dict[str, List[str]] = {}
    for r in csv.reader(io.StringIO(text)):
        if r[11] == "1":
            name = re.sub(r"（.*$", "", r[8])
            towns.setdefault(r[0] + _check_digit(r[0]), []).append(name)
    return towns, digest


ROMAN_URL = "https://www.post.japanpost.jp/service/search/zipcode/download/roman/KEN_ALL_ROME.zip"


def _romaji_tables(cache: Path) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, List[Tuple[str, str]]], str]:
    """Japan Post romanization: municipality code -> (pref, municipality) romaji, and town names with romaji."""
    import csv
    kana, _ = _download(POSTAL_URL, cache)
    roman, digest = _download(ROMAN_URL, cache)
    with zipfile.ZipFile(io.BytesIO(kana)) as zf:
        kana_rows = list(csv.reader(io.StringIO(zf.read(zf.namelist()[0]).decode("utf-8"))))
    with zipfile.ZipFile(io.BytesIO(roman)) as zf:
        roman_rows = list(csv.reader(io.StringIO(zf.read(zf.namelist()[0]).decode("cp932"))))
    lg_by = {(r[2], r[7].replace(" ", "")): r[0] + _check_digit(r[0]) for r in kana_rows}
    munis: Dict[str, Tuple[str, str]] = {}
    towns: Dict[str, List[Tuple[str, str]]] = {}
    for r in roman_rows:
        lg = lg_by.get((r[0], r[2].replace("\u3000", "").replace(" ", "")))
        if lg is None:
            continue
        munis.setdefault(lg, (r[4], r[5]))
        town = re.sub(r"[（(].*$", "", r[3]).replace("\u3000", "")
        town_r = re.sub(r"\(.*$", "", r[6]).strip()
        if town and town_r and "以下に掲載" not in town and "次に番地" not in town and not town.endswith("一円"):
            towns.setdefault(lg, []).append((town, town_r))
    return munis, towns, digest


def _english(romaji_words: str) -> List[str]:
    """'SAPPORO SHI CHUO KU' -> ['Chuo-ku', 'Sapporo-shi'] (English order)."""
    parts: List[str] = []
    for w in romaji_words.split():
        if w in ("SHI", "KU", "GUN", "MACHI", "CHO", "MURA", "SON") and parts:
            parts[-1] += "-" + w.lower()
        else:
            parts.append("-".join(p.capitalize() for p in w.split("-")))
    return list(reversed(parts))


def make_romaji(b: Dict[str, Any], rest: str, munis, towns) -> Optional[str]:
    if b["lg"] not in munis:
        return None
    m = re.match(r"(?P<town>.*?)(?P<num>\d+(?:-\d+)*)$", rest)
    if not m:
        return None
    best = max((t for t in towns.get(b["lg"], []) if m["town"] == t[0]), key=lambda t: len(t[0]), default=None)
    if best is None:
        return None
    pref_r, muni_r = munis[b["lg"]]
    pref = pref_r.split()[0].capitalize()
    town = " ".join("-".join(p.capitalize() for p in w.split("-")) for w in best[1].split())
    return ", ".join([f"{m['num']} {town}"] + _english(muni_r) + [pref])


def _has_chome(towns, town_text: str) -> bool:
    return any(town_text == t for t in towns)


def _load_registry() -> Dict[str, Dict[str, Any]]:
    sys.path.insert(0, str(HERE.parents[1] / "src"))
    from jaden.data.loader import get_registry
    reg = get_registry()
    return {m.lg_code: {"pref": m.prefecture_name, "name": m.name, "county": m.county,
                        "city": m.city, "ward": m.ward} for m in reg.list_municipalities()}


_TRIPLE = re.compile(r"(?P<pre>.*?)(?P<a>\d+)-(?P<b>\d+)-(?P<c>\d+)(?P<post>.*)$")
_PAIR = re.compile(r"(?P<pre>.*?)(?P<a>\d+)-(?P<b>\d+)(?P<post>.*)$")


def make_noisy(addr: str, prefix: str, chome_town: bool, rng: random.Random) -> str:
    """Applies one or more realistic formatting perturbations that keep the address meaning.

    The 丁目 rewrite is only applied where the first number is known to be a 丁目, so the
    perturbation never changes which place the address refers to.
    """
    out = addr
    m = _TRIPLE.match(out)
    choice = rng.randrange(4)
    if m and choice == 0 and chome_town:
        # 2-2-6 -> 二丁目2番6号
        out = f"{m['pre']}{_kanji_number(int(m['a']))}丁目{m['b']}番{m['c']}号{m['post']}"
    elif m and choice == 1:
        # 2-2-6 -> 2の2の6
        out = f"{m['pre']}{m['a']}の{m['b']}の{m['c']}{m['post']}"
    elif choice == 2:
        out = out.replace("-", rng.choice(["－", "ー", "‐", "−"]))
    # Full-width digits in most noisy items, and occasionally a space after the municipality
    if rng.random() < 0.7:
        out = unicodedata.normalize("NFKC", out).translate({ord(str(d)): chr(0xFF10 + d) for d in range(10)})
    if rng.random() < 0.3 and out.startswith(prefix):
        out = prefix + " " + out[len(prefix):]  # a space after the municipality, as typed in forms
    return out


def build(per_prefecture: int, seed: int, cache: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    registry = _load_registry()
    rng = random.Random(seed)
    sources = []
    base: List[Dict[str, Any]] = []
    dropped = {"code_not_in_registry": 0, "unexpected_prefix": 0, "duplicate": 0}
    seen = set()

    for pref in range(1, 48):
        url = SRC_URL.format(pref=pref)
        data, digest = _download(url, cache)
        sources.append({"url": url, "sha256": digest})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".geojson"))
            features = json.loads(zf.read(name))["features"]
        rows = []
        for ft in features:
            p = ft["properties"]
            code5, addr, school = p["P29_001"], (p["P29_005"] or "").strip(), p["P29_004"]
            lg = code5 + _check_digit(code5)
            muni = registry.get(lg)
            if muni is None:
                dropped["code_not_in_registry"] += 1
                continue
            addr = unicodedata.normalize("NFKC", addr).replace(" ", "")
            muni_full = (muni["county"] or "") + muni["name"]
            prefix = None
            for candidate in (muni["pref"] + muni_full, muni["pref"] + muni["name"]):
                if addr.startswith(candidate):
                    prefix = candidate
                    break
            if prefix is None or not re.search(r"\d", addr[len(prefix):]):
                dropped["unexpected_prefix"] += 1
                continue
            if addr in seen:
                dropped["duplicate"] += 1
                continue
            seen.add(addr)
            lon, lat = ft["geometry"]["coordinates"][:2]
            rows.append({"lg": lg, "addr": addr, "prefix": prefix, "pref": muni["pref"], "school": school,
                         "lat": round(lat, 6), "lon": round(lon, 6)})
        rng.shuffle(rows)
        base.extend(rows[:per_prefecture])

    chome_towns, postal_digest = _chome_towns(cache)
    sources.append({"url": POSTAL_URL, "sha256": postal_digest})
    roman_munis, roman_towns, roman_digest = _romaji_tables(cache)
    sources.append({"url": ROMAN_URL, "sha256": roman_digest})
    prefs = sorted({b["pref"] for b in base})
    items: List[Dict[str, Any]] = []

    def add(b: Dict[str, Any], variant: str, text: str, valid: bool) -> None:
        items.append({"id": f"{len(items):06d}", "variant": variant, "input": text, "valid": valid,
                      "gold_lg": b["lg"] if valid else None, "lat": b["lat"], "lon": b["lon"],
                      "source_lg": b["lg"]})

    for b in base:
        rest = b["addr"][len(b["prefix"]):]
        add(b, "original", b["addr"], True)
        add(b, "no_pref", b["addr"][len(b["pref"]):], True)
        add(b, "town_only", rest, True)
        m = _TRIPLE.match(rest)
        chome_town = bool(m) and _has_chome(chome_towns.get(b["lg"], ()), m["pre"])
        add(b, "noisy", make_noisy(b["addr"], b["prefix"], chome_town, rng), True)
        romaji = make_romaji(b, rest, roman_munis, roman_towns)
        if romaji:
            add(b, "romaji", romaji, True)

        other = rng.choice([p for p in prefs if p != b["pref"]])
        add(b, "wrong_pref", other + b["addr"][len(b["pref"]):], False)
        if m and chome_town:
            add(b, "chome_99", b["prefix"] + f"{m['pre']}99-{m['b']}-{m['c']}{m['post']}", False)
        add(b, "non_address", b["school"], False)

    meta = {
        "name": "JA-AddrBench",
        "version": "1.0",
        "seed": seed,
        "per_prefecture": per_prefecture,
        "base_addresses": len(base),
        "items": len(items),
        "variants": {v: sum(1 for i in items if i["variant"] == v) for v in
                     ("original", "no_pref", "town_only", "noisy", "romaji", "wrong_pref", "chome_99", "non_address")},
        "dropped_source_rows": dropped,
        "source": {"dataset": "国土数値情報 学校データ P29 (2023)", "landing_page": LANDING,
                   "license": "CC BY 4.0", "attribution": ATTRIBUTION, "files": sources},
    }
    return items, meta


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-prefecture", type=int, default=100)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "jaden" / "jabench")
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args(argv)
    items, meta = build(args.per_prefecture, args.seed, args.cache)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "jabench.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    with open(args.out / "jabench_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta["variants"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
