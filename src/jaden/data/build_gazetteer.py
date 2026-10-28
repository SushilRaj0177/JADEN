"""JADEN: Town gazetteer and postal-code dataset builder.

Downloads the official open datasets below, verifies and records their SHA256
digests, and compiles them into the compact files JADEN loads at runtime.

1. 大字・町丁目レベル位置参照情報 (MLIT, 国土交通省)
   Every registered town (大字・町丁目) in Japan with its representative point.
   https://nlftp.mlit.go.jp/isj/
   Terms (位置参照情報利用約款, 第2条): free use; derived works must cite
   "大字・町丁目レベル位置参照情報 国土交通省" together with the data year.

2. 郵便番号データ (Japan Post, 日本郵便)
   Postal codes with katakana readings (utf_ken_all) and romanized names
   (KEN_ALL_ROME). https://www.post.japanpost.jp/service/search/zipcode/download/
   Terms: "郵便番号データに限っては日本郵便株式会社は著作権を主張しません。
   自由に配布していただいて結構です。"

Outputs (written to the target directory):
- towns.tsv.gz   one row per registered town / 丁目
- postal.tsv.gz  one row per postal code area
- gazetteer_provenance.json  source URLs, versions, digests, counts

Usage:
    python -m jaden.data.build_gazetteer [--out DIR] [--cache DIR]
    jaden data update            (same, into the user data directory)
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any

from ..core.townkey import TOWN_KEY_VERSION, town_key, split_chome
from ..models.codes import calculate_modulus11_check_digit

ISJ_VERSION = "19.0b"
ISJ_DATA_YEAR = "2025"
ISJ_URL = "https://nlftp.mlit.go.jp/isj/dls/data/{ver}/{pref:02d}000-{ver}.zip"
ISJ_ATTRIBUTION = "大字・町丁目レベル位置参照情報 国土交通省"

# 街区レベル位置参照情報: one point per city block (住居表示 街区 or 地番), fetched per prefecture on request
BLOCK_VERSION = "24.0a"
BLOCK_URL = "https://nlftp.mlit.go.jp/isj/dls/data/{ver}/{pref:02d}000-{ver}.zip"
BLOCK_ATTRIBUTION = "街区レベル位置参照情報 国土交通省"
BLOCK_COLUMNS = ("lg_code", "key", "chome", "block", "lat", "lon", "jukyo")

POSTAL_BASE = "https://www.post.japanpost.jp/service/search/zipcode/download"
POSTAL_KANA_URL = f"{POSTAL_BASE}/utf/zip/utf_ken_all.zip"
POSTAL_ROMAN_URL = f"{POSTAL_BASE}/roman/KEN_ALL_ROME.zip"

USER_AGENT = "jaden-gazetteer-builder (+https://github.com/SushilRaj0177/JADEN)"

TOWN_COLUMNS = ("lg_code", "key", "machiaza_id", "name", "chome", "kind", "lat", "lon", "kana", "romaji")
POSTAL_COLUMNS = ("postal_code", "lg_code", "key", "town", "kana", "romaji", "kind", "chome")

# Japan Post placeholder town names that mean "the whole municipality"
_POSTAL_WHOLE_MUNI = re.compile(r"^(以下に掲載がない場合|.+の次に番地がくる場合|.+一円)$")
_PAREN = re.compile(r"[（(].*$")


def lg_code_for(base5: str) -> str:
    return base5 + calculate_modulus11_check_digit(base5)


def _download(url: str, cache_dir: Path, log: Callable[[str], None]) -> Tuple[bytes, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / url.rsplit("/", 1)[-1]
    if target.exists() and target.stat().st_size > 0:
        data = target.read_bytes()
    else:
        log(f"fetch {url}")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        target.write_bytes(data)
    return data, hashlib.sha256(data).hexdigest()


def _read_zip_csv(data: bytes, encoding: str) -> List[List[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        text = zf.read(name).decode(encoding)
    return list(csv.reader(io.StringIO(text)))


def _clean_postal_town(raw: str) -> Tuple[str, str]:
    """Returns (town_base, kind) for a Japan Post 町域 name."""
    if _POSTAL_WHOLE_MUNI.match(raw):
        return "", "municipality"
    kind = "building" if re.search(r"（(地階・階層不明|\d+階|.*階）)", raw) else "town"
    base = _PAREN.sub("", raw).replace("　", "").strip()
    return base, kind


def _clean_romaji(raw: str) -> str:
    return _PAREN.sub("", raw).strip()


_KANA_SUFFIX_ROMAJI = (("チョウ", "CHO"), ("マチ", "MACHI"), ("ムラ", "MURA"), ("ソン", "SON"), ("シ", "SHI"), ("ク", "KU"))


def _repair_truncated_suffix(romaji: str, kana: str) -> str:
    """Japan Post cuts long romaji ('...KAWAGUCHIKO MAC'); restore the 町/村 suffix from the kana."""
    if romaji.rpartition(" ")[2] in {ro for _, ro in _KANA_SUFFIX_ROMAJI}:
        return romaji
    suffix = next((ro for ka, ro in _KANA_SUFFIX_ROMAJI if kana.endswith(ka)), None)
    if suffix is None or romaji.endswith(" " + suffix):
        return romaji
    head, _, last = romaji.rpartition(" ")
    if head and suffix.startswith(last):
        return f"{head} {suffix}"
    return f"{romaji} {suffix}"


def build(out_dir: Path, cache_dir: Path, log: Callable[[str], None] = print) -> Dict[str, Any]:
    sources: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ MLIT
    towns: List[Dict[str, Any]] = []
    seen_ids = set()
    for pref in range(1, 48):
        url = ISJ_URL.format(ver=ISJ_VERSION, pref=pref)
        data, digest = _download(url, cache_dir / "isj", log)
        sources.append({"url": url, "sha256": digest, "bytes": len(data)})
        rows = _read_zip_csv(data, "cp932")
        for r in rows[1:]:
            name = r[5]
            # The MLIT files repeat a handful of rows verbatim; keep the first
            if not name or name.startswith("（") or r[4] in seen_ids:
                continue
            seen_ids.add(r[4])
            base, chome = split_chome(name)
            towns.append({
                "lg_code": lg_code_for(r[2]),
                "key": town_key(base),
                "machiaza_id": r[4],
                "name": base,
                "chome": chome,
                "kind": r[9],  # 1 大字, 2 字, 3 丁目, 0 unknown
                "lat": r[6],
                "lon": r[7],
            })
    log(f"MLIT towns: {len(towns)}")

    # ------------------------------------------------------------ Japan Post
    kana_zip, kana_digest = _download(POSTAL_KANA_URL, cache_dir / "postal", log)
    rome_zip, rome_digest = _download(POSTAL_ROMAN_URL, cache_dir / "postal", log)
    sources.append({"url": POSTAL_KANA_URL, "sha256": kana_digest, "bytes": len(kana_zip)})
    sources.append({"url": POSTAL_ROMAN_URL, "sha256": rome_digest, "bytes": len(rome_zip)})
    kana_rows = _read_zip_csv(kana_zip, "utf-8")
    rome_rows = _read_zip_csv(rome_zip, "cp932")

    # Postal codes are shared between neighbouring municipalities, so joins use code + municipality + town
    def _muni(name: str) -> str:
        return name.replace("　", "").replace(" ", "")

    romaji_by_postal_town: Dict[Tuple[str, str, str], str] = {}
    for r in rome_rows:
        base, _ = _clean_postal_town(r[3].replace("　", ""))
        romaji_by_postal_town.setdefault((r[0], _muni(r[2]), town_key(base)), _clean_romaji(r[6]))

    postal: List[Dict[str, Any]] = []
    reading_by_town: Dict[Tuple[str, str], Tuple[str, str]] = {}
    municipality_readings: Dict[str, Dict[str, str]] = {}
    for r in kana_rows:
        lg = lg_code_for(r[0])
        base, kind = _clean_postal_town(r[8])
        kana = _PAREN.sub("", unicodedata.normalize("NFKC", r[5])).strip() if base else ""
        romaji = romaji_by_postal_town.get((r[2], _muni(r[7]), town_key(base)), "") if base else ""
        postal.append({"postal_code": r[2], "lg_code": lg, "key": town_key(base), "town": base, "kana": kana,
                       "romaji": romaji, "kind": kind, "chome": r[11]})
        if base and kind == "town":
            reading_by_town.setdefault((lg, town_key(base)), (kana, romaji))
        if lg not in municipality_readings:
            municipality_readings[lg] = {"kana": unicodedata.normalize("NFKC", r[4])}
    # ROME rows carry no municipality code; pair each with its KEN_ALL row by postal code + town
    lg_by_postal_muni = {(r[2], _muni(r[7])): lg_code_for(r[0]) for r in kana_rows}
    for r in rome_rows:
        rome_lg = lg_by_postal_muni.get((r[0], _muni(r[2])))
        if rome_lg and "romaji" not in municipality_readings.get(rome_lg, {}):
            entry = municipality_readings.setdefault(rome_lg, {})
            entry["romaji"] = _repair_truncated_suffix(r[5].strip(), entry.get("kana", ""))
            entry["prefecture_romaji"] = r[4].strip()
    log(f"Japan Post rows: {len(postal)}")

    # Attach readings to MLIT towns where the town names agree
    matched = 0
    for t in towns:
        reading = reading_by_town.get((t["lg_code"], town_key(t["name"])))
        if reading:
            t["kana"], t["romaji"] = reading
            matched += 1
        else:
            t["kana"], t["romaji"] = "", ""
    log(f"towns with readings: {matched}/{len(towns)}")

    # ---------------------------------------------------------------- output
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_tsv(out_dir / "towns.tsv.gz", TOWN_COLUMNS, towns)
    _write_tsv(out_dir / "postal.tsv.gz", POSTAL_COLUMNS, postal)
    with open(out_dir / "municipality_readings.json", "w", encoding="utf-8") as f:
        json.dump(municipality_readings, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    provenance = {
        "built": date.today().isoformat(),
        "town_key_version": TOWN_KEY_VERSION,
        "towns": {
            "dataset": f"大字・町丁目レベル位置参照情報 {ISJ_VERSION} ({ISJ_DATA_YEAR}年版)",
            "publisher": "国土交通省 不動産・建設経済局 (MLIT)",
            "landing_page": "https://nlftp.mlit.go.jp/isj/",
            "terms": "https://nlftp.mlit.go.jp/isj/agreement.html",
            "attribution": f"「{ISJ_ATTRIBUTION}」{ISJ_DATA_YEAR}年版 ({ISJ_VERSION}) を加工して作成",
            "records": len(towns),
            "records_with_readings": matched,
        },
        "postal": {
            "dataset": "郵便番号データ (読み仮名データ UTF-8 版 / ローマ字版)",
            "publisher": "日本郵便株式会社 (Japan Post)",
            "landing_page": "https://www.post.japanpost.jp/zipcode/download.html",
            "terms": "郵便番号データに限っては日本郵便株式会社は著作権を主張しません。自由に配布していただいて結構です。",
            "records": len(postal),
        },
        "sources": sources,
    }
    with open(out_dir / "gazetteer_provenance.json", "w", encoding="utf-8") as f:
        json.dump(provenance, f, ensure_ascii=False, indent=2)
    return provenance


def build_blocks(pref: int, out_dir: Path, cache_dir: Path, log: Callable[[str], None] = print) -> Dict[str, Any]:
    """Compiles MLIT block-level points for one prefecture into blocks/NN.tsv.gz."""
    from .loader import get_registry

    registry = get_registry()
    url = BLOCK_URL.format(ver=BLOCK_VERSION, pref=pref)
    data, digest = _download(url, cache_dir / "isj_blocks", log)
    rows = _read_zip_csv(data, "cp932")
    pref_code = f"{pref:02d}"
    lg_by_name = {m.name: m.lg_code for m in registry.list_municipalities(pref_code)}
    for m in registry.list_municipalities(pref_code):
        if m.county:
            lg_by_name.setdefault(m.county + m.name, m.lg_code)

    blocks: List[Dict[str, Any]] = []
    unmatched: Dict[str, int] = {}
    for r in rows[1:]:
        if r[11] != "1":  # representative point of each block only
            continue
        muni = r[1].replace("\u3000", "").replace(" ", "")
        lg = lg_by_name.get(muni)
        if lg is None:
            unmatched[muni] = unmatched.get(muni, 0) + 1
            continue
        base, chome = split_chome(r[2])
        if not r[4].isdigit():
            continue
        blocks.append({"lg_code": lg, "key": town_key(base + r[3]), "chome": chome, "block": int(r[4]),
                       "lat": r[8], "lon": r[9], "jukyo": r[10]})
    blocks.sort(key=lambda b: (b["lg_code"], b["key"], b["chome"] or 0, b["block"]))

    target = out_dir / "blocks"
    target.mkdir(parents=True, exist_ok=True)
    _write_tsv(target / f"{pref_code}.tsv.gz", BLOCK_COLUMNS, blocks)
    meta = {
        "dataset": f"街区レベル位置参照情報 {BLOCK_VERSION}",
        "attribution": f"「{BLOCK_ATTRIBUTION}」{BLOCK_VERSION} を加工して作成",
        "terms": "https://nlftp.mlit.go.jp/isj/agreement.html",
        "url": url, "sha256": digest, "records": len(blocks),
        "unmatched_municipalities": unmatched, "town_key_version": TOWN_KEY_VERSION,
        "built": date.today().isoformat(),
    }
    with open(target / f"{pref_code}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    log(f"blocks {pref_code}: {len(blocks)} points, {sum(unmatched.values())} rows in unknown municipalities")
    return meta


def _write_tsv(path: Path, columns: Tuple[str, ...], rows: List[Dict[str, Any]]) -> None:
    # mtime=0 keeps the archive byte-identical across rebuilds of the same data
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz:
        with io.TextIOWrapper(gz, encoding="utf-8", newline="\n") as f:
            f.write("\t".join(columns) + "\n")
            for row in rows:
                f.write("\t".join("" if row[c] is None else str(row[c]) for c in columns) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build JADEN's town gazetteer from official open data.")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent, help="output directory")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "jaden" / "downloads",
                        help="download cache directory")
    parser.add_argument("--blocks", type=int, nargs="*", metavar="PREF",
                        help="also build block-level points for these prefecture codes (1-47)")
    args = parser.parse_args(argv)
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    if args.blocks is not None and len(args.blocks) > 0:
        for pref in args.blocks:
            build_blocks(pref, args.out, args.cache, log=log)
        return 0
    prov = build(args.out, args.cache, log=log)
    print(json.dumps({k: prov[k]["records"] for k in ("towns", "postal")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
