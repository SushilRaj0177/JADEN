"""Converts geolonia_run.mjs output to the evaluator's format ({"id", "lg_code", "lat", "lon"}).

Geolonia returns names, not codes; a result counts as an answer when it resolved the
municipality (level >= 2), and the (prefecture, city) names are mapped to the MIC code.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jaden.data.loader import get_registry  # noqa: E402


def main(raw_path: str, out_path: str) -> None:
    reg = get_registry()
    by_name = {}
    for m in reg.list_municipalities():
        by_name[(m.prefecture_name, m.name)] = m.lg_code
        if m.county:
            by_name[(m.prefecture_name, m.county + m.name)] = m.lg_code
    with open(raw_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            r = json.loads(line)
            lg = None
            if r.get("level", 0) >= 2:
                lg = by_name.get((r.get("pref"), (r.get("city") or "").replace(" ", "")))
            point = r.get("point") or {}
            out.write(json.dumps({"id": r["id"], "lg_code": lg,
                                  "lat": point.get("lat") if lg else None,
                                  "lon": point.get("lng") if lg else None}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
