"""Builds the inputs of held-out test 2 (PROTOCOL.md) from the MHLW medical facility tables.

  download   fetches the five frozen files into DATA/medical and checks their SHA-256
  inputs     writes DIR/inputs.jsonl and DIR/summary.json

Each input row: {"id", "variant", "input", "side", "truth", "category", "lat", "lon", "unseen"},
where truth is the five-digit municipality code (prefecture code + 3-digit code) and unseen says
that the full address matches no development address (see PROTOCOL.md).

Usage:
    python benchmarks/heldout2/make_inputs.py download [--data ~/.cache/jaden-realdata]
    python benchmarks/heldout2/make_inputs.py inputs --out DIR [--data ...]
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Set

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks" / "realdata"))
sys.path.insert(0, str(ROOT / "benchmarks" / "heldout"))

BASE = "https://www.mhlw.go.jp/content/11121000/"
FILES = {
    "hospital": ("01-1_hospital_facility_info_20260601.csv.zip",
                 "b416472ec52a151455e1c91438e0dec5b471e19eafe70e3e2ee1bb22544efe87"),
    "clinic": ("02-1_clinic_facility_info_20260601.csv.zip",
               "602be1310990fc557cfca8cda0e84494304e4df8581c1aca218b68327ebea2cf"),
    "dental": ("03-1_dental_facility_info_20260601.csv.zip",
               "1585ea00b981df8c32d93850b2321a27053b8a9af3d46afc18df11af1f022727"),
    "maternity": ("04_maternity_home_20260601.csv.zip",
                  "27cc63ed72913f95d8da48cef2287246bbfc6f25f414caa94fc226524d6eb87a"),
    "pharmacy": ("05_pharmacy_20260601.csv.zip",
                 "e53eacdbd9b4a11593cfe89f9a8b57a62f62a1e066751d42c73591b6818f9bf4"),
}
VARIANTS = ("full", "no prefecture", "town only")


def download(data: Path) -> None:
    folder = data / "medical"
    folder.mkdir(parents=True, exist_ok=True)
    for name, sha in FILES.values():
        target = folder / name
        if not target.exists():
            with urllib.request.urlopen(BASE + name, timeout=300) as r:
                target.write_bytes(r.read())
        got = hashlib.sha256(target.read_bytes()).hexdigest()
        if got != sha:
            raise SystemExit(f"{name}: SHA-256 {got} is not the frozen {sha}")
        print(f"{name}: ok")


def rows(data: Path) -> Iterator[Dict[str, Any]]:
    for kind, (name, _sha) in FILES.items():
        with zipfile.ZipFile(data / "medical" / name) as z:
            inner = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(inner) as fh:
                for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")):
                    yield {"key": f"{kind}:{r['ID']}", "kind": kind,
                           "pref": (r.get("都道府県コード") or "").strip(), "muni": (r.get("市区町村コード") or "").strip(),
                           "address": (r.get("所在地") or "").strip(),
                           "name": (r.get("正式名称") or r.get("名称") or "").strip(),
                           "lat": (r.get("所在地座標（緯度）") or "").strip(), "lon": (r.get("所在地座標（経度）") or "").strip()}


def dev_key(text: str) -> bytes:
    squashed = "".join(unicodedata.normalize("NFKC", text).split())
    return hashlib.blake2b(squashed.encode("utf-8"), digest_size=8).digest()


def development_keys(data: Path) -> Set[bytes]:
    """Every development address (PROTOCOL.md, 'unseen'), hashed."""
    import evaluate_care
    import evaluate_companies
    import make_inputs as welfare
    keys: Set[bytes] = set()
    for _id, pref, city, address, _kata, *_ in evaluate_care.read_rows(data / "care"):
        keys.update((dev_key(address), dev_key(pref + city + address), dev_key(evaluate_care.compose(pref, city, address))))
    print(f"  care: {len(keys):,} keys", file=sys.stderr)
    for _num, pref, city, street, _code, _postal in evaluate_companies.read_rows(data / "companies" / "zenkoku.zip"):
        keys.add(dev_key(pref + city + street))
    print(f"  + companies: {len(keys):,} keys", file=sys.stderr)
    for r in welfare.rows(data / "welfare" / "P14-23_GML.zip"):
        keys.add(dev_key(r["pref"] + r["city"] + r["address"]))
    print(f"  + welfare: {len(keys):,} keys", file=sys.stderr)
    return keys


def strip_heads(address: str, m: Any) -> Dict[str, Optional[str]]:
    """The no-prefecture and town-only texts, or None where the address does not start as expected."""
    if not address.startswith(m.prefecture_name):
        return {"no prefecture": None, "town only": None}
    rest = address[len(m.prefecture_name):]
    no_pref = rest or None
    if m.county and rest.startswith(m.county):
        rest = rest[len(m.county):]
    town = rest[len(m.name):] if rest.startswith(m.name) else None
    return {"no prefecture": no_pref, "town only": town or None}


def build(data: Path, out: Path) -> None:
    from jaden.data.loader import get_registry
    by5 = {m.lg_code[:5]: m for m in get_registry().list_municipalities()}
    keys = development_keys(data)
    out.mkdir(parents=True, exist_ok=True)
    counts: Counter = Counter()
    with open(out / "inputs.jsonl", "w", encoding="utf-8") as fh:
        for r in rows(data):
            counts["rows"] += 1
            counts[f"rows: {r['kind']}"] += 1
            if not r["address"]:
                counts["excluded: no address"] += 1
                continue
            m = by5.get(r["pref"].zfill(2) + r["muni"].zfill(3)) if len(r["muni"]) == 3 else None
            if m is None:
                counts["excluded: municipality code not current or missing"] += 1
                continue
            unseen = dev_key(r["address"]) not in keys
            counts["unseen"] += unseen
            texts = {"full": r["address"], **strip_heads(r["address"], m)}
            for v in VARIANTS:
                if texts[v] is None:
                    counts[f"no {v} input"] += 1
                    continue
                counts[f"inputs: {v}"] += 1
                fh.write(json.dumps({"id": f"{r['key']}:{v}", "variant": v, "input": texts[v], "side": r["name"],
                                     "truth": m.lg_code[:5], "category": r["kind"], "lat": r["lat"], "lon": r["lon"],
                                     "unseen": unseen}, ensure_ascii=False) + "\n")
    (out / "summary.json").write_text(json.dumps(dict(counts), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False, indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["download", "inputs"])
    ap.add_argument("--data", type=Path, default=Path.home() / ".cache" / "jaden-realdata")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.stage == "download":
        download(args.data)
    else:
        if args.out is None:
            ap.error("inputs needs --out")
        build(args.data, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
