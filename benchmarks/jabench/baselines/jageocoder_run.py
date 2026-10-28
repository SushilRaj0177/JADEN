"""Runs jageocoder over JA-AddrBench and writes {"id", "lg_code", "lat", "lon"} JSONL.

    pip install jageocoder
    jageocoder install-dictionary gaiku_all_v22.20260417.zip   # https://www.info-proto.com/static/jageocoder/latest/
    python jageocoder_run.py ../jabench.jsonl jageocoder.jsonl

A result counts as an answer when the best match reaches at least the municipality level.
"""

import json
import sys

import jageocoder


def check_digit(d5: str) -> str:
    r = sum(int(d) * w for d, w in zip(d5, (6, 5, 4, 3, 2))) % 11
    return str((11 - r) % 10) if r <= 1 else str(11 - r)


def main(in_path: str, out_path: str) -> None:
    jageocoder.init()
    with open(in_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            item = json.loads(line)
            lg = lat = lon = None
            results = jageocoder.searchNode(item["input"])
            if results:
                node = results[0].node
                jis = node.get_city_jiscode()
                if jis:
                    lg = jis + check_digit(jis)
                    lat, lon = node.y, node.x
            out.write(json.dumps({"id": item["id"], "lg_code": lg, "lat": lat, "lon": lon}) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
