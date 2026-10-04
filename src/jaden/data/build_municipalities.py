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
- License: Government Open Data (Ministry of Internal Affairs and Communications Terms of Use / CC BY 4.0 compatible)
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
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any

SOURCE_METADATA = {
    "source_organization": "Ministry of Internal Affairs and Communications (総務省自治行政局)",
    "dataset_name": "都道府県コード及び市区町村コード (令和6年1月1日更新)",
    "source_url": "https://www.soumu.go.jp/main_content/000925835.xlsx",
    "source_file_sha256": "7d04c8a7f6a6e76a7823a0414a8422bf2b26bb6070766971df76eab58ea6ff78",
    "effective_date": "2024-01-01",
    "retrieval_date": "2026-10-04",
    "standards": ["JIS X 0401:1973", "JIS X 0402:2020"],
    "counts": {
        "prefectures": 47,
        "municipalities": 1747,
        "special_wards": 23,
        "designated_cities": 20,
        "standard_cities": 772,
        "towns": 743,
        "villages": 189,
        "administrative_wards": 171,
        "total_bundled_records": 1918
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
            val = v.text if v is not None else ""
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
    with zipfile.ZipFile(xlsx_path) as z:
        strings = parse_xlsx_shared_strings(z)
        s1_rows = parse_sheet_rows(z, "xl/worksheets/sheet1.xml", strings)[1:]  # skip header
        s2_rows = parse_sheet_rows(z, "xl/worksheets/sheet2.xml", strings)[1:]  # skip header

    # Step 1: Identify 20 designated cities from Sheet 2
    designated_cities_set = set()
    for r in s2_rows:
        name = r.get("C", "").strip()
        if name.endswith("市"):
            designated_cities_set.add(name)

    records: List[Dict[str, Any]] = []

    # Step 2: Parse Sheet 1 (Standard Municipalities)
    for r in s1_rows:
        code_raw = r.get("A", "").strip()
        pref_name = r.get("B", "").strip()
        muni_name = r.get("C", "").strip()
        pref_kana = r.get("D", "").strip()
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
            "county": None,
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


if __name__ == "__main__":
    data_dir = Path(__file__).parent
    xlsx_file = data_dir / "soumu_000925835.xlsx"
    out_json = data_dir / "municipalities.json"
    out_meta = data_dir / "provenance.json"

    print(f"Building municipalities dataset from {xlsx_file}...")
    recs = build_municipalities_dataset(xlsx_file, out_json, out_meta)
    print(f"Successfully generated {len(recs)} verified records at {out_json}")
    print(f"Metadata generated at {out_meta}")
