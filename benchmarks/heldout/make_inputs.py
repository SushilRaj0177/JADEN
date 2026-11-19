"""Builds the held-out test inputs from the MLIT welfare-facility file (see PROTOCOL.md).

For every facility with an address: 'town only' (the address as published, without the
municipality), 'with prefecture' and 'full' (prefecture + municipality + address), each with
the facility name as side information. Writes JSONL rows
    {"id", "variant", "input", "side", "truth", "category", "lat", "lon"}
where truth is the five-digit municipality code from the file.

Usage:
    python benchmarks/heldout/make_inputs.py [--data ~/.cache/jaden-realdata] --out DIR
"""

import argparse
import io
import json
import zipfile
from pathlib import Path

VARIANTS = ("town only", "with prefecture", "full")


def rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(n for n in z.namelist() if n.endswith("_GML.zip")):
            inner = zipfile.ZipFile(io.BytesIO(z.read(name)))
            geojson = next(n for n in inner.namelist() if n.endswith(".geojson"))
            for i, f in enumerate(json.loads(inner.read(geojson))["features"]):
                p = f["properties"]
                address = (p.get("P14_004") or "").strip()
                if not address:
                    continue
                lon, lat = f["geometry"]["coordinates"][:2]
                yield {"key": f"{name.rsplit('/', 1)[-1][:9]}:{i}", "pref": p["P14_001"], "city": p["P14_002"] or "",
                       "address": address, "side": p.get("P14_008") or "", "truth": p["P14_003"],
                       "category": p["P14_005"], "lat": lat, "lon": lon}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path.home() / ".cache" / "jaden-realdata")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(args.out / "inputs.jsonl", "w", encoding="utf-8") as fh:
        for r in rows(args.data / "welfare" / "P14-23_GML.zip"):
            texts = {"town only": r["address"], "with prefecture": r["pref"] + r["address"],
                     "full": r["pref"] + r["city"] + r["address"]}
            for v in VARIANTS:
                fh.write(json.dumps({"id": f"{r['key']}:{v}", "variant": v, "input": texts[v], "side": r["side"],
                                     "truth": r["truth"], "category": r["category"], "lat": r["lat"],
                                     "lon": r["lon"]}, ensure_ascii=False) + "\n")
                n += 1
    print(f"{n:,} inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
