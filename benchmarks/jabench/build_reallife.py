"""JA-AddrBench real-life robustness set.

Takes the `original` addresses of jabench.jsonl and adds what addresses look like on
real forms, CRM exports and shipping labels. The address itself is never changed, so a
robust system must return the same municipality and the same canonical address as for
the clean input, and must separate the added building, floor and room correctly.

Perturbations (each applied to every base address, deterministic per seed):
  room_hyphen     '…2-2-6-305'                  room as a fourth block number (after N-N-N only)
  building_room   '…2-2-6 メゾン桜302'            building with the room glued on
  building_floor  '…2-2-6 第2田中ビル 3F'         building and floor
  room_label      '…2-2-6 405号室'                room with 号室
  english_unit    '…2-2-6 Apt 1203'              English unit label
  spaced          '福岡県 糸島市 前原東2-2-6'      spaces between components
  form_label      '住所：〒 福岡県…'               form label / country prefix
  fullwidth       '…２－２－６'                    full-width digits and dash

Usage:
    python benchmarks/jabench/build_reallife.py
Writes benchmarks/jabench/reallife.jsonl.
"""

import json
import random
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from jaden.data.loader import get_registry  # noqa: E402

REGISTRY = get_registry()

_BUILDING_STEMS = ["メゾン", "ハイツ", "コーポ", "レジデンス", "パークハウス", "グランドメゾン", "シティハイツ", "サンハイツ",
                   "ロイヤルマンション", "エステート", "プラザ", "ヴィラ", "フラット", "カーサ", "パレス"]
_BUILDING_NAMES = ["桜", "青葉", "若葉", "富士見", "朝日", "緑", "中央", "駅前", "第二", "ひまわり", "けやき", "グリーン",
                   "サンライズ", "リバーサイド", "田中"]
_OFFICE = ["第2田中ビル", "朝日生命ビル", "駅前センタービル", "第一ビル", "中央ビルディング", "NSビル", "ツインタワー"]
_LABELS = ["住所：", "住所:", "ご住所 ", "お届け先：", "日本 ", "日本、", "Japan "]


def _prefix(addr: str, lg: str):
    m = REGISTRY.get_municipality_by_code(lg)
    for muni in ((m.county or "") + m.name, m.name):
        if addr.startswith(m.prefecture_name + muni):
            return m.prefecture_name, muni
    return m.prefecture_name, ""


def main() -> int:
    rng = random.Random(7)
    base = [json.loads(line) for line in open(HERE / "jabench.jsonl", encoding="utf-8")]
    base = [b for b in base if b["variant"] == "original"]
    items = []

    def add(b, variant, text, building=None, floor=None, unit=None):
        items.append({"id": f"R{len(items):06d}", "variant": variant, "base": b["input"], "input": text,
                      "gold_lg": b["gold_lg"], "building": building, "floor": floor, "unit": unit})

    for b in base:
        addr = b["input"]
        if re.search(r"\d+-\d+-\d+-\d+", addr):
            continue  # the published address already carries a room number
        room = str(rng.choice([101, 102, 201, 203, 302, 305, 405, 501, 703, 1203, 1505]))
        name = rng.choice(_BUILDING_STEMS) + rng.choice(_BUILDING_NAMES)
        if re.search(r"(?<![\d-])\d+-\d+-\d+$", addr):
            # Only after a full 丁目-番-号 / three-part number; after '188' the room would read as a lot
            add(b, "room_hyphen", f"{addr}-{room}", unit=room)
        add(b, "building_room", f"{addr} {name}{room}", building=name, unit=room)
        office, fl = rng.choice(_OFFICE), f"{rng.randint(1, 12)}F"
        add(b, "building_floor", f"{addr} {office} {fl}", building=office, floor=fl)
        add(b, "room_label", f"{addr} {room}号室", unit=f"{room}号室")
        add(b, "english_unit", f"{addr} Apt {room}", unit=room)
        add(b, "spaced", _spaced(addr, _prefix(addr, b["gold_lg"])))
        add(b, "form_label", rng.choice(_LABELS) + addr)
        add(b, "fullwidth", unicodedata.normalize("NFKC", addr).translate(
            {**{ord(str(d)): chr(0xFF10 + d) for d in range(10)}, ord("-"): "－"}))

    with open(HERE / "reallife.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} items", file=sys.stderr)
    return 0


def _spaced(addr: str, prefix_parts) -> str:
    """Spaces after the prefecture and the municipality, as typed into separate form fields."""
    pref, muni = prefix_parts
    if addr.startswith(pref + muni):
        return f"{pref} {muni} {addr[len(pref) + len(muni):]}"
    return addr


if __name__ == "__main__":
    sys.exit(main())
