"""Runs jageocoder and keeps every equally good match, so that it can abstain like JADEN.

jageocoder's searchNode returns all nodes whose matched text is equally long (for `錦町1-2`, twenty
towns called 錦町). `jageocoder_run.py` keeps the first; this runner keeps the municipality of every
node that matched the longest text, and writes

    {"id", "lg_codes": [distinct six-digit codes, in jageocoder's order], "top": first code or null}

A jageocoder that abstains then answers only when `lg_codes` holds one municipality. Codes are mapped
to the current MIC list exactly as in `jageocoder_run.py`.

    python jageocoder_candidates_run.py inputs.jsonl out.jsonl [processes] [--variants "town only,..."]
"""

import json
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, List, Optional

import jageocoder

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jageocoder_run import check_digit, current  # noqa: E402


_CACHE: Dict[int, Optional[str]] = {}


def _code(node: Any) -> Optional[str]:
    """The node's municipality code, cached by node id (the same towns come back again and again)."""
    key = node.id
    if key not in _CACHE:
        _CACHE[key] = _code_uncached(node)
    return _CACHE[key]


def _code_uncached(node: Any) -> Optional[str]:
    jis = node.get_city_jiscode()
    if not jis:
        return None
    lg = jis + check_digit(jis)
    codes, names = current()
    if lg not in codes:
        from geolonia_to_jsonl import fold
        parents = {p.level: p.name for p in node.get_parent_list()}
        name = parents.get(3, "") + parents.get(4, "")
        lg = names.get((parents.get(1, ""), fold(name)), f"unknown:{parents.get(1, '')}{name}")
    return lg


def run(items: List[Dict[str, Any]]) -> List[str]:
    if not jageocoder.is_initialized():
        jageocoder.init()
    out = []
    for item in items:
        results = jageocoder.searchNode(item["input"])
        lgs: List[str] = []
        if results and results[0].matched:
            best = len(results[0].matched)
            for r in results:
                if len(r.matched) != best:
                    continue
                lg = _code(r.node)
                if lg and lg not in lgs:
                    lgs.append(lg)
        out.append(json.dumps({"id": item["id"], "lg_codes": lgs, "top": lgs[0] if lgs else None}, ensure_ascii=False))
    return out


def main(argv: List[str]) -> None:
    in_path, out_path = argv[0], argv[1]
    processes = int(argv[2]) if len(argv) > 2 and not argv[2].startswith("--") else 1
    variants = None
    if "--variants" in argv:
        variants = set(argv[argv.index("--variants") + 1].split(","))
    with open(in_path, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    if variants:
        items = [it for it in items if it.get("variant") in variants]
    batches = [items[i:i + 2000] for i in range(0, len(items), 2000)]
    with open(out_path, "w", encoding="utf-8") as out, Pool(processes) as pool:
        for done, lines in enumerate(pool.imap(run, batches), 1):
            out.write("\n".join(lines) + "\n")
            if done % 20 == 0:
                print(f"{done * 2000:,} / {len(items):,}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
