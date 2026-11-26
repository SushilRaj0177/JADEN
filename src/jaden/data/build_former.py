"""JADEN: Former municipality names (平成の大合併 and later reorganizations).

Old addresses keep municipality names that no longer exist: 浦和市 (now さいたま市),
清水市 (now 静岡市清水区), 浜松市中区 (abolished 2024). This builder maps every
former name to the current municipalities its area now belongs to.

Sources:
1. 国土数値情報 行政区域 N03 (MLIT), 2000-10-01 boundaries, CC BY 4.0.
   Every current MLIT town point is placed inside the 2000 boundaries; a former
   municipality's successors are the current municipalities of the towns inside it.
   This also records splits (part of a town went one way, part another).
2. 都道府県コード及び市区町村コード 改正一覧表 (MIC), all changes since 2005-04-01,
   for municipalities created after 2000 and abolished again, renames, and the
   2024 Hamamatsu ward reorganization.

Output, bundled with the package:
    former_municipalities.json   former names with their successors and abolition dates, and every retired
                                 code with its current successors (code_changes)
    former_districts.tsv.gz      every current district point inside a former municipality, with that
                                 municipality's 2000 code

Usage:
    python -m jaden.data.build_former [--out DIR] [--cache DIR]
"""

import argparse
import gzip
import hashlib
import io
import json
import re
import struct
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any

N03_YEAR = "2000"
N03_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2000/N03-001001_{pref:02d}_GML.zip"
N03_ATTRIBUTION = "「国土数値情報（行政区域データ）」（国土交通省）（2000年10月1日時点）を加工して作成"
MIC_CHANGES_URL = "https://www.soumu.go.jp/main_content/000875488.xlsx"
USER_AGENT = "jaden-gazetteer-builder (+https://github.com/SushilRaj0177/JADEN)"

# A successor holding less than this share of a former municipality's towns is boundary noise
_MIN_SHARE = 0.03

Ring = List[Tuple[float, float]]


def _download(url: str, cache_dir: Path, log: Callable[[str], None]) -> Tuple[bytes, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / url.rsplit("/", 1)[-1]
    if not target.exists():
        log(f"fetch {url}")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=180) as resp:
            target.write_bytes(resp.read())
    data = target.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------- shapefiles
def read_dbf(data: bytes, encoding: str = "cp932") -> List[Dict[str, str]]:
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    for i in range(32, header_len - 1, 32):
        fields.append((data[i:i + 11].split(b"\0")[0].decode("ascii"), data[i + 16]))
    rows = []
    for r in range(count):
        rec = data[header_len + r * record_len: header_len + (r + 1) * record_len]
        pos, row = 1, {}
        for name, length in fields:
            row[name] = rec[pos:pos + length].decode(encoding, "replace").strip()
            pos += length
        rows.append(row)
    return rows


def read_polygons(data: bytes) -> List[Tuple[Tuple[float, float, float, float], List[Ring]]]:
    """Polygon (type 5) records of a .shp file as (bbox, rings) with (lon, lat) points."""
    out: List[Tuple[Tuple[float, float, float, float], List[Ring]]] = []
    pos = 100
    while pos < len(data):
        _, length = struct.unpack(">ii", data[pos:pos + 8])
        content = data[pos + 8: pos + 8 + 2 * length]
        pos += 8 + 2 * length
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type != 5:
            out.append(((0.0, 0.0, 0.0, 0.0), []))
            continue
        bbox = struct.unpack("<4d", content[4:36])
        n_parts, n_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{n_parts}i", content[44:44 + 4 * n_parts])) + [n_points]
        coords_at = 44 + 4 * n_parts
        flat = struct.unpack(f"<{2 * n_points}d", content[coords_at:coords_at + 16 * n_points])
        points = list(zip(flat[0::2], flat[1::2]))
        rings = [points[parts[i]:parts[i + 1]] for i in range(n_parts)]
        out.append((bbox, rings))
    return out


def inside(x: float, y: float, rings: List[Ring]) -> bool:
    """Even-odd rule over all rings (holes included)."""
    hit = False
    for ring in rings:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
    return hit


def _check_digit(d5: str) -> str:
    r = sum(int(d) * w for d, w in zip(d5, (6, 5, 4, 3, 2))) % 11
    return str((11 - r) % 10) if r <= 1 else str(11 - r)


# ------------------------------------------------------------- N03 overlay
def former_from_boundaries(town_points: Dict[str, List[Tuple[str, float, float, str, str]]], registry, cache: Path,
                           log: Callable[[str], None]
                           ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], Dict[Tuple[str, str, str], str]]:
    """Former municipalities (2000-10-01) with their current successors, the sources, and for every current
    district point (lg_code, town key, 丁目) the 2000 municipality code it lies in."""
    entries: List[Dict[str, Any]] = []
    sources = []
    districts: Dict[Tuple[str, str, str], str] = {}
    current = {m.lg_code: m for m in registry.list_municipalities()}
    for pref in range(1, 48):
        url = N03_URL.format(pref=pref)
        data, digest = _download(url, cache / "n03-2000", log)
        sources.append({"url": url, "sha256": digest})
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            shp = next(n for n in zf.namelist() if n.endswith(".shp"))
            dbf = next(n for n in zf.namelist() if n.endswith(".dbf"))
            polygons = read_polygons(zf.read(shp))
            rows = read_dbf(zf.read(dbf))
        # One former municipality may span several polygons (islands)
        by_code: Dict[str, Dict[str, Any]] = {}
        for (bbox, rings), row in zip(polygons, rows):
            code = row.get("N03_007", "")
            if not code or not rings:
                continue
            item = by_code.setdefault(code, {"row": row, "shapes": []})
            item["shapes"].append((bbox, rings))
        counts: Dict[str, Dict[str, int]] = {code: {} for code in by_code}
        for lg, lon, lat, key, chome in town_points.get(f"{pref:02d}", []):
            for code, item in by_code.items():
                if any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and inside(lon, lat, rings)
                       for b, rings in item["shapes"]):
                    counts[code][lg] = counts[code].get(lg, 0) + 1
                    districts[(lg, key, chome)] = code + _check_digit(code)
                    break
        for code, item in by_code.items():
            row = item["row"]
            total = sum(counts[code].values())
            if not total:
                continue
            successors = {lg: n for lg, n in counts[code].items() if n / total >= _MIN_SHARE}
            name = row["N03_004"]
            group = row["N03_003"]  # 郡 or designated city
            lg_2000 = code + _check_digit(code)
            same = current.get(lg_2000)
            full = (group + name) if group and not group.endswith("郡") else name
            if same is not None and same.name == full and set(successors) <= {lg_2000}:
                continue  # unchanged municipality
            entries.append({
                "pref": f"{pref:02d}", "name": full, "county": group if group.endswith("郡") else "",
                "former_code": lg_2000, "successors": successors, "as_of": "2000-10-01",
            })
        log(f"N03-2000 {pref:02d}: {len(by_code)} municipalities, {sum(1 for e in entries if e['pref'] == f'{pref:02d}')} changed")
    return entries, sources, districts


# ---------------------------------------------------------------- MIC list
def former_from_mic_changes(data: bytes, registry) -> List[Dict[str, Any]]:
    """(prefecture, former name) -> successor names, from the MIC 改正一覧表."""
    from .build_municipalities import parse_xlsx_shared_strings, parse_sheet_rows
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        rows = parse_sheet_rows(zf, "xl/worksheets/sheet1.xml", parse_xlsx_shared_strings(zf))
    pref_codes = {p.name: p.code for p in registry.list_all_prefectures()}
    pref = ""
    pending: List[Tuple[str, str]] = []      # deleted, waiting for the next 新設 row
    group_successor: Optional[str] = None
    last = ""
    city_of_ward = ""
    links: List[Tuple[str, str, List[str], str]] = []   # (pref, old, [new names], reason)
    for r in rows[4:]:
        e, old, kind = r.get("E", "").strip(), r.get("G", "").strip(), r.get("I", "").strip()
        new_name, reason = r.get("K", "").strip(), r.get("M", "").strip()
        if e in pref_codes:
            pref = e
        if kind == "欠番" or (kind == "〃" and last == "deleted"):
            merged = re.search(r"合併後は(.+?)(?:$|[（(、])", reason)
            if merged:
                group_successor = merged.group(1).strip()
                pending = []
            elif reason and kind == "欠番":
                group_successor = None
                pending = []
            if group_successor:
                links.append((pref, old, [group_successor], "merger"))
            else:
                pending.append((pref, old))
            last = "deleted"
        elif kind == "新設" or (kind == "〃" and last == "new"):
            if pending:
                for p, o in pending:
                    if reason == "" and new_name.endswith("区") and city_of_ward:
                        links.append((p, o, [city_of_ward + new_name], "reorganization"))
                    else:
                        links.append((p, o, [new_name], "status change"))
                if not new_name.endswith("区"):
                    city_of_ward = new_name
                    pending = []
            last = "new"
        elif r.get("J", "").strip() == "同左" and reason == "名称変更" and new_name and new_name != "同左":
            links.append((pref, old, [new_name], "rename"))
            last = ""
        else:
            last = ""
            if kind == "" and r.get("J", "").strip() == "同左":
                city_of_ward = old

    entries = []
    for p, old, news, why in links:
        if not old or p not in pref_codes:
            continue
        entries.append({"pref": pref_codes[p], "name": old.replace(" ", "").replace("　", ""),
                        "successor_names": news, "reason": why})
    return entries


_ERAS = {"H": 1988, "R": 2018}


def _mic_date(value: str) -> str:
    """'39173' (an Excel day number), 'H23.10.11' or 'R6.1.1' as an ISO date; '' when not a date."""
    value = value.strip()
    if re.fullmatch(r"\d{5}", value):
        return date.fromordinal(date(1899, 12, 30).toordinal() + int(value)).isoformat()
    m = re.fullmatch(r"([HR])(\d+)\.(\d+)\.(\d+)", value)
    if m:
        return date(_ERAS[m.group(1)] + int(m.group(2)), int(m.group(3)), int(m.group(4))).isoformat()
    return ""


def deleted_codes_from_mic(data: bytes, registry) -> List[Dict[str, str]]:
    """Every code the MIC 改正一覧表 deletes: prefecture, old code, old name, date and reason.

    The codes one change deletes stand in consecutive rows (the first says 欠番, the others 〃), and the
    reason is written across those rows in pieces ('合併後は' / '石狩市'); each code gets the whole text.
    A row continues the previous one's prefecture and date when it says 〃 or leaves them empty.
    """
    from .build_municipalities import parse_xlsx_shared_strings, parse_sheet_rows
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        rows = parse_sheet_rows(zf, "xl/worksheets/sheet1.xml", parse_xlsx_shared_strings(zf))
    pref_codes = {p.name: p.code for p in registry.list_all_prefectures()}
    pref, when, last_kind = "", "", ""
    out: List[Dict[str, str]] = []
    group: List[Dict[str, str]] = []
    pieces: List[str] = []

    def close() -> None:
        # a piece cut mid-sentence ('合併後は' / '石狩市') continues directly; whole pieces are separated
        text = ""
        for piece in pieces:
            text += piece if not text or text[-1] in "はのをにと、及" else "; " + piece
        for item in group:
            item["reason"] = text
        group.clear()
        pieces.clear()

    for r in rows[4:]:
        e, code, name, kind = (r.get(c, "").strip() for c in ("E", "F", "G", "I"))
        reason, raw_date = r.get("M", "").strip(), r.get("N", "").strip()
        if e in pref_codes:
            pref = e
        if raw_date and raw_date != "〃":
            when = _mic_date(raw_date)
        deleted = kind == "欠番" or (kind == "〃" and last_kind == "deleted")
        if kind == "欠番" or (kind and not deleted):
            close()
        if kind:
            last_kind = "deleted" if deleted else ("new" if kind == "新設" or (kind == "〃" and last_kind == "new") else "")
        if deleted:
            if reason and reason != "〃":
                pieces.append(reason)
            if re.fullmatch(r"\d{6}", code) and pref in pref_codes:
                item = {"pref": pref_codes[pref], "code": code, "name": name.replace(" ", "").replace("　", ""),
                        "date": when, "reason": ""}
                group.append(item)
                out.append(item)
    close()
    return out


def _hamamatsu_wards(registry) -> List[Dict[str, Any]]:
    """The 2024-01-01 reorganization lists its successors only as prose; the old wards map to the new ones."""
    by_name = {m.name: m.lg_code for m in registry.list_municipalities("22")}
    new = {w: by_name[f"浜松市{w}"] for w in ("中央区", "浜名区", "天竜区") if f"浜松市{w}" in by_name}
    plan = {"中区": ["中央区"], "東区": ["中央区"], "西区": ["中央区"], "南区": ["中央区"],
            "北区": ["中央区", "浜名区"], "浜北区": ["浜名区"], "天竜区": ["天竜区"]}
    return [{"pref": "22", "name": f"浜松市{old}", "county": "", "successors": {new[w]: 1 for w in wards if w in new},
             "as_of": "2023-12-31", "reason": "ward reorganization 2024-01-01"}
            for old, wards in plan.items() if old != "天竜区"]


def build(out_dir: Path, cache: Path, log: Callable[[str], None] = print) -> Dict[str, Any]:
    from .loader import get_registry
    registry = get_registry()

    town_points: Dict[str, List[Tuple[str, float, float, str, str]]] = {}
    with gzip.open(out_dir / "towns.tsv.gz", "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t")
            lg, lat, lon = parts[0], float(parts[6]), float(parts[7])
            town_points.setdefault(lg[:2], []).append((lg, lon, lat, parts[1], parts[4]))

    entries, sources, districts = former_from_boundaries(town_points, registry, cache, log)

    mic_data, mic_digest = _download(MIC_CHANGES_URL, cache / "mic", log)
    sources.append({"url": MIC_CHANGES_URL, "sha256": mic_digest})
    current_by_name: Dict[Tuple[str, str], List[str]] = {}
    for m in registry.list_municipalities():
        current_by_name.setdefault((m.prefecture_code, m.name), []).append(m.lg_code)
        if m.ward:
            current_by_name.setdefault((m.prefecture_code, m.city + m.ward), []).append(m.lg_code)
    mic = former_from_mic_changes(mic_data, registry)
    successor_names = {(e["pref"], e["name"]): e["successor_names"] for e in mic}

    def resolve(pref: str, name: str, depth: int = 0) -> List[str]:
        if (pref, name) in current_by_name:
            return current_by_name[(pref, name)]
        if depth > 6 or (pref, name) not in successor_names:
            return []
        out: List[str] = []
        for nxt in successor_names[(pref, name)]:
            out += [lg for lg in resolve(pref, nxt, depth + 1) if lg not in out]
        return out

    known = {(e["pref"], e["name"]) for e in entries}
    for e in mic:
        key = (e["pref"], e["name"])
        if key in known or key in current_by_name:
            continue
        lgs = resolve(*key)
        if lgs:
            entries.append({"pref": e["pref"], "name": e["name"], "county": "", "successors": {lg: 1 for lg in lgs},
                            "as_of": "after 2005-04-01", "reason": e["reason"]})
            known.add(key)
    for e in _hamamatsu_wards(registry):
        if (e["pref"], e["name"]) not in current_by_name:
            entries = [x for x in entries if (x["pref"], x["name"]) != (e["pref"], e["name"])] + [e]

    # Names that are still current are handled by the municipality registry itself
    entries = [e for e in entries if (e["pref"], e["name"]) not in current_by_name]
    entries.sort(key=lambda e: (e["pref"], e["name"]))

    # Retired codes: every code the MIC list deletes, with its current successors and the date
    deleted = deleted_codes_from_mic(mic_data, registry)
    by_former_code = {e["former_code"]: e for e in entries if e.get("former_code")}
    by_former_name = {(e["pref"], e["name"]): e for e in entries}
    current_codes = {m.lg_code for m in registry.list_municipalities()}
    # 浜松市, 2024-01-01: the old ward codes; 天竜区 kept its name but got a new code
    hama_new = {m.name: m.lg_code for m in registry.list_municipalities("22") if m.city == "浜松市"}
    hama_plan = {"中区": ["中央区"], "東区": ["中央区"], "西区": ["中央区"], "南区": ["中央区"],
                 "北区": ["中央区", "浜名区"], "浜北区": ["浜名区"], "天竜区": ["天竜区"]}
    code_changes: List[Dict[str, Any]] = []
    unresolved = []
    for d in deleted:
        if d["code"] in current_codes:
            continue
        merged = re.search(r"合併後は(.+?)(?:$|[（(、。])", d["reason"])
        if d["pref"] == "22" and d["code"].startswith("2213") and d["name"] in hama_plan:
            successors = sorted(hama_new[f"浜松市{w}"] for w in hama_plan[d["name"]] if f"浜松市{w}" in hama_new)
            d = dict(d, date=d["date"] or "2024-01-01")
        elif d["code"] in by_former_code:
            successors = sorted(by_former_code[d["code"]]["successors"])
        elif (d["pref"], d["name"]) in by_former_name:
            successors = sorted(by_former_name[(d["pref"], d["name"])]["successors"])
        else:
            successors = resolve(d["pref"], d["name"])
        if not successors and merged:
            successors = resolve(d["pref"], merged.group(1).strip())
        if not successors:
            unresolved.append(d)
            continue
        code_changes.append({"code": d["code"], "name": d["name"], "pref": d["pref"], "successors": successors,
                             "date": d["date"], "reason": d["reason"]})
    dates = {c["code"]: c["date"] for c in code_changes}
    dates_by_name = {(c["pref"], c["name"]): c["date"] for c in code_changes}
    for e in entries:
        if e.get("former_code"):
            # in the MIC list (changes since 2005-04-01) or changed between the 2000 boundaries and then
            e["abolished"] = (dates.get(e["former_code"]) or dates_by_name.get((e["pref"], e["name"]))
                              or "2000-10-01/2005-03-31")
    for d in unresolved:
        log(f"  no current successor found for {d['code']} {d['name']} ({d['reason']})")
    code_changes.sort(key=lambda c: c["code"])
    log(f"retired codes: {len(code_changes)} mapped, {len(unresolved)} without a current successor")

    # Every current district inside a former municipality, with that municipality's 2000 code
    changed = {e["former_code"]: e["name"] for e in entries if e.get("former_code")}
    with gzip.open(out_dir / "former_districts.tsv.gz", "wt", encoding="utf-8") as f:
        f.write("lg_code\tkey\tchome\tformer_code\tformer_name\n")
        for (d_lg, d_key, d_chome), former in sorted(districts.items()):
            if former in changed:
                f.write(f"{d_lg}\t{d_key}\t{d_chome}\t{former}\t{changed[former]}\n")

    result = {
        "built": date.today().isoformat(),
        "attribution": [N03_ATTRIBUTION, "「都道府県コード及び市区町村コード」改正一覧表（総務省）を加工して作成"],
        "sources": sources,
        "entries": entries,
        "code_changes": code_changes,
    }
    with open(out_dir / "former_municipalities.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    log(f"former municipalities: {len(entries)}")
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Build JADEN's former municipality names.")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent)
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "jaden" / "downloads")
    args = ap.parse_args(argv)
    build(args.out, args.cache, log=lambda m: print(m, file=sys.stderr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
