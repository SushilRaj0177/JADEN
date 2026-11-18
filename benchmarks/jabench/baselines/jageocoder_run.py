"""Runs jageocoder over a JSONL file of {"id", "input"} and writes {"id", "lg_code", "lat", "lon"} JSONL.

    pip install jageocoder
    jageocoder install-dictionary gaiku_all_v22.20260417.zip   # https://www.info-proto.com/static/jageocoder/latest/
    python jageocoder_run.py ../jabench.jsonl jageocoder.jsonl [processes]

A result counts as an answer when the best match reaches at least the municipality level.
When nothing in the text matches, jageocoder still returns a node with an empty matched
string; that is not an answer.

jageocoder's dictionary can carry a code that has since been replaced while the name is
current (浜松市天竜区 under 22137, renumbered 22140 in 2024). A code that is not in the
current MIC list is therefore mapped by the municipality's name, as for Geolonia; a name
that is not current either (浜松市中区, abolished in 2024) is kept as "unknown:<name>".
"""

import json
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jageocoder

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geolonia_to_jsonl import fold  # noqa: E402
from jaden.data.loader import get_registry  # noqa: E402

_CURRENT: Optional[Tuple[set, Dict[Tuple[str, str], str]]] = None


def current() -> Tuple[set, Dict[Tuple[str, str], str]]:
    global _CURRENT
    if _CURRENT is None:
        codes, names = set(), {}
        for m in get_registry().list_municipalities():
            codes.add(m.lg_code)
            names[(m.prefecture_name, fold(m.name))] = m.lg_code
        _CURRENT = (codes, names)
    return _CURRENT


def check_digit(d5: str) -> str:
    r = sum(int(d) * w for d, w in zip(d5, (6, 5, 4, 3, 2))) % 11
    return str((11 - r) % 10) if r <= 1 else str(11 - r)


def run(items: List[Dict[str, Any]]) -> List[str]:
    if not jageocoder.is_initialized():
        jageocoder.init()
    out = []
    for item in items:
        lg = lat = lon = None
        results = jageocoder.searchNode(item["input"])
        if results and results[0].matched:
            node = results[0].node
            jis = node.get_city_jiscode()
            if jis:
                lg = jis + check_digit(jis)
                lat, lon = node.y, node.x
                codes, names = current()
                if lg not in codes:
                    parents = {p.level: p.name for p in node.get_parent_list()}
                    name = parents.get(3, "") + parents.get(4, "")
                    lg = names.get((parents.get(1, ""), fold(name)), f"unknown:{parents.get(1, '')}{name}")
        out.append(json.dumps({"id": item["id"], "lg_code": lg, "lat": lat, "lon": lon}))
    return out


def main(in_path: str, out_path: str, processes: int = 1) -> None:
    with open(in_path, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    batches = [items[i:i + 2000] for i in range(0, len(items), 2000)]
    with open(out_path, "w", encoding="utf-8") as out:
        if processes <= 1:
            results = map(run, batches)
            for lines in results:
                out.write("\n".join(lines) + "\n")
        else:
            with Pool(processes) as pool:
                for done, lines in enumerate(pool.imap(run, batches), 1):
                    out.write("\n".join(lines) + "\n")
                    if done % 20 == 0:
                        print(f"{done * 2000:,} / {len(items):,}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
