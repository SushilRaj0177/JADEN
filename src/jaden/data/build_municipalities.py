"""JADEN: Authoritative dataset builder for Japanese municipalities.

Ingests and validates official Local Government Codes (全国地方公共団体コード)
directly from the Ministry of Internal Affairs and Communications (MIC / 総務省)
authoritative dataset (令和6年1月1日更新 / Jan 1, 2024).

Provenance & Metadata:
- Issuing Body: Ministry of Internal Affairs and Communications (MIC / 総務省自治行政局)
- Dataset Name: 都道府県コード及び市区町村コード (令和6年1月1日更新)
- Source URL: https://www.soumu.go.jp/main_content/000925835.xlsx
- Source File: soumu_000925835.xlsx
- SHA256: 7d04c8a7f6a6e76a7823a0414a8422bf2b26bb6070766971df76eab58ea6ff78
- Retrieval Date: 2026-10-04
- Terms: Users should consult the Ministry of Internal Affairs and Communications' own terms of use on their official website
- Verified Standard: JIS X 0401:1973 (Prefectures) & JIS X 0402:2020 (Municipalities, Modulus 11)

Entity Breakdown:
- Prefectures: 47
- Municipalities (Sheet 1): 1,747
  - Special Wards (東京都特別区): 23
  - Designated Cities (政令指定都市): 20
  - Standard Cities (市): 772
  - Towns (町): 743
  - Villages (村): 189 (including Northern Territories / 北方領土 6村)
- Administrative Wards (Sheet 2, 行政区): 171 (reflecting Jan 1, 2024 Hamamatsu consolidation)
Total Municipal Records Bundled: 1,918
"""

import json
import re
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from typing import Callable, Dict, List, Any, Optional, Tuple

SOURCE_METADATA: Dict[str, Any] = {
    "source_organization": "Ministry of Internal Affairs and Communications (総務省自治行政局)",
    "dataset_name": "都道府県コード及び市区町村コード (令和6年1月1日更新)",
    "source_url": "https://www.soumu.go.jp/main_content/000925835.xlsx",
    "source_file_sha256": "7d04c8a7f6a6e76a7823a0414a8422bf2b26bb6070766971df76eab58ea6ff78",
    "effective_date": "2024-01-01",
    "retrieval_date": "2026-10-04",
    "standards": ["JIS X 0401:1973", "JIS X 0402:2020"],
    "county_source": "Japan Post Address Base Registry (日本郵便 郵便番号データ) & Northern Territories Statutory Administrative Districts (北方領土地方自治法定義町村)",
    "counts": {
        "prefectures": 47,
        "municipalities": 1747,
        "special_wards": 23,
        "designated_cities": 20,
        "standard_cities": 772,
        "towns": 743,
        "villages": 189,
        "administrative_wards": 171,
        "total_bundled_records": 1918,
        "counties_mapped": 923,
        "island_municipalities_without_county": 9
    }
}


def calc_check_digit(d5: str) -> str:
    """Calculates official Modulus 11 check digit for 5-digit base code."""
    weights = [6, 5, 4, 3, 2]
    s = sum(int(d) * w for d, w in zip(d5, weights))
    r = s % 11
    if r <= 1:
        return str((11 - r) % 10)
    return str(11 - r)


def parse_xlsx_shared_strings(z: zipfile.ZipFile) -> List[str]:
    """Extracts shared strings from OpenXML without ruby phonetic (<rPh>) pollution."""
    sst_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings = []
    for si in sst_root.findall("s:si", ns):
        direct_t = si.find("s:t", ns)
        if direct_t is not None:
            strings.append(direct_t.text or "")
        else:
            r_texts = [t.text or "" for r in si.findall("s:r", ns) for t in r.findall("s:t", ns)]
            strings.append("".join(r_texts))
    return strings


def parse_sheet_rows(z: zipfile.ZipFile, sheet_path: str, strings: List[str]) -> List[Dict[str, str]]:
    """Parses row cells into column dictionaries."""
    tree = ET.fromstring(z.read(sheet_path))
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for r in tree.findall(".//s:row", ns):
        cells = {}
        for c in r.findall("s:c", ns):
            col = "".join(ch for ch in c.attrib.get("r", "") if ch.isalpha())
            t = c.attrib.get("t")
            v = c.find("s:v", ns)
            val = (v.text or "") if v is not None else ""
            if t == "s" and val:
                val = strings[int(val)]
            cells[col] = val
        if cells:
            rows.append(cells)
    return rows


def build_municipalities_dataset(
    xlsx_path: Path,
    output_json_path: Path,
    metadata_json_path: Path
) -> List[Dict[str, Any]]:
    """Parses official MIC Excel file into verified municipalities.json."""
    from ..xlsx import _open_part
    with zipfile.ZipFile(xlsx_path) as z:
        for part in ("xl/sharedStrings.xml", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
            _open_part(z, part, xlsx_path).close()    # size, compression ratio and DTD checks before parsing
        strings = parse_xlsx_shared_strings(z)
        s1_rows = parse_sheet_rows(z, "xl/worksheets/sheet1.xml", strings)[1:]  # skip header
        s2_rows = parse_sheet_rows(z, "xl/worksheets/sheet2.xml", strings)[1:]  # skip header

    # Step 1: Identify 20 designated cities from Sheet 2
    designated_cities_set = set()
    for r in s2_rows:
        name = r.get("C", "").strip()
        if name.endswith("市"):
            designated_cities_set.add(name)

    # Load county mapping for towns and villages
    county_mapping_file = Path(__file__).parent / "county_mapping.json"
    county_map: Dict[str, Optional[str]] = {}
    if county_mapping_file.exists():
        with open(county_mapping_file, "r", encoding="utf-8") as f:
            county_map = json.load(f)

    records: List[Dict[str, Any]] = []

    # Step 2: Parse Sheet 1 (Standard Municipalities)
    for r in s1_rows:
        code_raw = r.get("A", "").strip()
        pref_name = r.get("B", "").strip()
        muni_name = r.get("C", "").strip()
        muni_kana = r.get("E", "").strip()

        # Prefectural summary rows have empty muni_name
        if not muni_name:
            continue

        base_code = code_raw[:5]
        cd = code_raw[5]
        expected_cd = calc_check_digit(base_code)
        if cd != expected_cd:
            raise ValueError(f"Check digit mismatch for {code_raw} ({muni_name}): got {cd}, expected {expected_cd}")

        pref_code = code_raw[:2]

        # Determine entity type
        if pref_name == "東京都" and muni_name.endswith("区"):
            entity_type = "special_ward"
        elif muni_name in designated_cities_set:
            entity_type = "designated_city"
        elif muni_name.endswith("市"):
            entity_type = "city"
        elif muni_name.endswith("町"):
            entity_type = "town"
        elif muni_name.endswith("村"):
            entity_type = "village"
        else:
            raise ValueError(f"Unrecognized entity suffix for {code_raw}: {muni_name}")

        records.append({
            "prefecture_code": pref_code,
            "prefecture_name": pref_name,
            "base_code": base_code,
            "check_digit": cd,
            "lg_code": code_raw,
            "name": muni_name,
            "city": muni_name,
            "ward": None,
            "county": county_map.get(base_code),
            "entity_type": entity_type,
            "kana": muni_kana
        })

    # Step 3: Parse Sheet 2 (Administrative Wards of Designated Cities)
    for r in s2_rows:
        code_raw = r.get("A", "").strip()
        pref_name = r.get("B", "").strip()
        full_name = r.get("C", "").strip()
        muni_kana = r.get("E", "").strip()

        # Skip city headers (already captured in Sheet 1)
        if full_name.endswith("市"):
            continue

        base_code = code_raw[:5]
        cd = code_raw[5]
        expected_cd = calc_check_digit(base_code)
        if cd != expected_cd:
            raise ValueError(f"Check digit mismatch for ward {code_raw} ({full_name}): got {cd}, expected {expected_cd}")

        pref_code = code_raw[:2]

        # Parse city and ward: e.g. "札幌市中央区" -> city="札幌市", ward="中央区"
        # Find which designated city this belongs to
        parent_city = None
        ward_name = None
        for d_city in designated_cities_set:
            if full_name.startswith(d_city):
                parent_city = d_city
                ward_name = full_name[len(d_city):]
                break

        if not parent_city or not ward_name:
            raise ValueError(f"Could not separate city and ward for designated city ward: {full_name}")

        records.append({
            "prefecture_code": pref_code,
            "prefecture_name": pref_name,
            "base_code": base_code,
            "check_digit": cd,
            "lg_code": code_raw,
            "name": full_name,
            "city": parent_city,
            "ward": ward_name,
            "county": None,
            "entity_type": "administrative_ward",
            "kana": muni_kana
        })

    # Verify counts
    assert len(records) == 1918, f"Expected 1918 records, got {len(records)}"

    # Sort deterministically by 6-digit Local Government Code
    records.sort(key=lambda x: x["lg_code"])

    # Write output files
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with open(metadata_json_path, "w", encoding="utf-8") as f:
        json.dump(SOURCE_METADATA, f, ensure_ascii=False, indent=2)

    return records


MIC_INDEX_URL = "https://www.soumu.go.jp/denshijiti/code.html"
_CODE_LIST_LINK = re.compile(
    r"都道府県コード及び市区町村コード.{0,200}?（(?P<label>[^）]{2,40}更新)）.{0,400}?href=\"(?P<href>[^\"]+\.xlsx)\"",
    re.DOTALL)


def decode_page(raw: bytes) -> str:
    """MIC's pages are Shift_JIS; the charset is taken from the page when it says so."""
    m = re.search(rb"charset=[\"']?([A-Za-z0-9_-]+)", raw[:2000])
    for enc in ([m.group(1).decode("ascii")] if m else []) + ["utf-8", "cp932", "euc_jp"]:
        try:
            return raw.decode("cp932" if enc.lower() in ("shift_jis", "sjis", "x-sjis") else enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def find_latest_list(html: str) -> Optional[Tuple[str, str]]:
    """(xlsx URL, '令和6年1月1日更新') of the current code list on MIC's code page."""
    text = re.sub(r"<(?!a\s)[^>]+>", " ", html)          # keep the links, drop other tags
    m = _CODE_LIST_LINK.search(text)
    if m is None:
        return None
    href = m.group("href")
    url = href if href.startswith("http") else "https://www.soumu.go.jp" + ("" if href.startswith("/") else "/") + href
    return url, m.group("label")


def refresh(out_dir: Path, cache_dir: Path, log: Callable[[str], None] = print,
            index_html: Optional[str] = None) -> Dict[str, Any]:
    """Downloads MIC's current municipality code list and, when it differs from the bundled one, writes
    municipalities.json to ``out_dir`` (which the registry then reads instead of the bundled copy).
    Returns what was done: {'changed': bool, 'url', 'label', 'sha256', 'records', 'added', 'removed'}."""
    import hashlib
    import os
    import urllib.request
    from datetime import date
    from .build_gazetteer import USER_AGENT, _download

    if index_html is None:
        req = urllib.request.Request(MIC_INDEX_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            index_html = decode_page(resp.read())
    found = find_latest_list(index_html)
    if found is None:
        raise RuntimeError(f"no municipality code list (.xlsx) found on {MIC_INDEX_URL}")
    url, label = found
    data, digest = _download(url, cache_dir, log)
    out_dir.mkdir(parents=True, exist_ok=True)
    target, meta_target = out_dir / "municipalities.json", out_dir / "municipalities_provenance.json"
    result: Dict[str, Any] = {"url": url, "label": label, "sha256": digest}
    if digest == SOURCE_METADATA["source_file_sha256"]:
        for stale in (target, meta_target):     # an older refresh is superseded by the bundled list
            if stale.exists():
                stale.unlink()
        log(f"municipality list unchanged ({label}); using the bundled copy")
        return {**result, "changed": False, "records": SOURCE_METADATA["counts"]["total_bundled_records"],
                "added": [], "removed": []}

    xlsx = cache_dir / url.rsplit("/", 1)[-1]
    tmp_json, tmp_meta = target.with_suffix(".json.tmp"), meta_target.with_suffix(".json.tmp")
    try:
        records = build_municipalities_dataset(xlsx, tmp_json, tmp_meta)
    except (KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        tmp_json.unlink(missing_ok=True)
        tmp_meta.unlink(missing_ok=True)
        raise RuntimeError(f"could not read {url} ({exc}); the bundled list stays in use") from None
    prefectures = {r["prefecture_code"] for r in records}
    if len(records) < 1700 or len(prefectures) != 47:
        tmp_json.unlink(missing_ok=True)
        tmp_meta.unlink(missing_ok=True)
        raise RuntimeError(f"the downloaded list looks wrong ({len(records)} records, {len(prefectures)} prefectures); "
                           "the bundled list stays in use")
    bundled = json.loads((Path(__file__).parent / "municipalities.json").read_text(encoding="utf-8"))
    old = {r["lg_code"]: r["name"] for r in bundled}
    new = {r["lg_code"]: r["name"] for r in records}
    added = sorted(f"{c} {n}" for c, n in new.items() if c not in old)
    removed = sorted(f"{c} {n}" for c, n in old.items() if c not in new)
    no_county = sum(1 for r in records if r["entity_type"] in ("town", "village") and not r.get("county")
                    and r["lg_code"] not in old)
    provenance = {"source_url": url, "dataset_name": f"都道府県コード及び市区町村コード ({label})",
                  "source_file_sha256": hashlib.sha256(data).hexdigest(), "retrieval_date": date.today().isoformat(),
                  "records": len(records), "added": added, "removed": removed}
    tmp_meta.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_json, target)
    os.replace(tmp_meta, meta_target)
    log(f"municipality list updated to {label}: {len(records)} records, {len(added)} added, {len(removed)} removed"
        + (f"; {no_county} new towns or villages have no county yet" if no_county else ""))
    return {**result, "changed": True, "records": len(records), "added": added, "removed": removed}


if __name__ == "__main__":
    data_dir = Path(__file__).parent
    xlsx_file = data_dir / "soumu_000925835.xlsx"
    out_json = data_dir / "municipalities.json"
    out_meta = data_dir / "provenance.json"

    print(f"Building municipalities dataset from {xlsx_file}...")
    recs = build_municipalities_dataset(xlsx_file, out_json, out_meta)
    print(f"Successfully generated {len(recs)} verified records at {out_json}")
    print(f"Metadata generated at {out_meta}")
