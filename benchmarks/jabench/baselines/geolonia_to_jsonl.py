"""Converts geolonia_run.mjs output to the evaluator's format ({"id", "lg_code", "lat", "lon"}).

Geolonia returns names, not codes; a result counts as an answer when it resolved the
municipality (level >= 2), and the (prefecture, city) names are mapped to the MIC code.
Names are compared after folding variant characters (ヶ/ケ, 﨑/崎 ...), so a spelling
difference between Geolonia's data and the MIC list does not turn an answer into a miss.
A name that still maps to no current municipality is kept as an answer with the code
"unknown:<name>" and listed at the end, so it is scored as wrong rather than as no answer.
"""

import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from jaden.data.loader import get_registry  # noqa: E402

_FOLD = str.maketrans({"ヶ": "ケ", "ヵ": "ケ", "が": "ケ", "ガ": "ケ", "の": "ノ", "﨑": "崎", "嶋": "島",
                       "澤": "沢", "濱": "浜", "邊": "辺", "邉": "辺", "齋": "斎", "國": "国", "竈": "釜", "諌": "諫", "檮": "梼"})


def fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace(" ", "").replace("　", "").translate(_FOLD)


def main(raw_path: str, out_path: str) -> None:
    reg = get_registry()
    by_name = {}
    for m in reg.list_municipalities():
        by_name[(m.prefecture_name, fold(m.name))] = m.lg_code
        if m.county:
            by_name[(m.prefecture_name, fold(m.county + m.name))] = m.lg_code
    unknown: Counter = Counter()
    errors = 0
    with open(raw_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            r = json.loads(line)
            errors += "error" in r
            lg = None
            if r.get("level", 0) >= 2 and r.get("city"):
                lg = by_name.get((r.get("pref"), fold(r["city"])))
                if lg is None:
                    unknown[(r.get("pref"), r["city"])] += 1
                    lg = f"unknown:{r.get('pref')}{r['city']}"
            point = r.get("point") or {}
            out.write(json.dumps({"id": r["id"], "lg_code": lg,
                                  "lat": point.get("lat") if lg else None,
                                  "lon": point.get("lng") if lg else None}, ensure_ascii=False) + "\n")
    if errors:
        print(f"{errors} inputs raised an error (counted as no answer)", file=sys.stderr)
    for (pref, city), n in unknown.most_common():
        print(f"no current municipality named {pref}{city}: {n}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
