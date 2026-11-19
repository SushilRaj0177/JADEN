"""A language model as the last step of address resolution, and alone.

  choose  the model sees the address, the organisation's name and JADEN's candidate
          municipalities, numbered; it answers with one number, or 0 when it cannot tell.
          Only a number from the list can come back, so it cannot name a place JADEN did not
          verify.
  free    the same address and name, no candidates: the model names the municipality itself.
          Its answer is mapped to the MIC list by name; a name that is no municipality is an
          invented one.

The model is called through the Claude Code command line (`claude -p`), 20 addresses per call,
with a fixed prompt. Each call's prompt and raw answer are kept, so the run can be audited.

Usage:
    python benchmarks/heldout/llm.py choose ITEMS.jsonl OUT.jsonl [--model claude-haiku-5-5] [--jobs 4]
    python benchmarks/heldout/llm.py free   ITEMS.jsonl OUT.jsonl
ITEMS rows: {"id", "input", "side", "candidates": [six-digit codes]} (candidates only for choose).
"""

import argparse
import json
import subprocess
import sys
import tempfile
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

BATCH = 20

CHOOSE_PROMPT = """You are resolving Japanese addresses that do not say which municipality they are in.
For each item you get the address, the name of the organisation at that address, and a numbered
list of the municipalities whose registered towns match the address. Pick the municipality the
organisation is most likely in, using every clue (place names in the organisation's name, how
common each place is, the address itself). If the clues do not point to one municipality, answer 0.
Do not explain. Reply with one JSON object per line and nothing else:
{"id": "<item id>", "choice": <number from the list, or 0>, "confidence": <0-100>}

"""

FREE_PROMPT = """You are resolving Japanese addresses that do not say which municipality they are in.
For each item you get the address and the name of the organisation at that address. Name the
prefecture and the municipality (市区町村; for a designated city, the city and ward) the
organisation is most likely in. If you cannot tell, give empty strings.
Do not explain. Reply with one JSON object per line and nothing else:
{"id": "<item id>", "prefecture": "<e.g. 東京都>", "municipality": "<e.g. 練馬区 or 札幌市中央区>", "confidence": <0-100>}

"""


def municipality_label(lg: str, by_code: Dict[str, Any]) -> str:
    m = by_code[lg]
    return f"{m.prefecture_name}{m.county or ''}{m.name}"


def prompt_for(mode: str, items: List[Dict[str, Any]], by_code: Dict[str, Any]) -> str:
    parts = [CHOOSE_PROMPT if mode == "choose" else FREE_PROMPT]
    for it in items:
        parts.append(f"id: {it['id']}\naddress: {it['input']}\norganisation: {it['side'] or '(none)'}")
        if mode == "choose":
            parts.append("\n".join(f"  {i}. {municipality_label(lg, by_code)}" for i, lg in enumerate(it["candidates"], 1)))
        parts.append("")
    return "\n".join(parts)


def call_model(prompt: str, model: str) -> str:
    with tempfile.TemporaryDirectory() as cwd:   # an empty directory: no project files or settings
        out = subprocess.run(["claude", "-p", "--model", model, "--output-format", "text"], input=prompt,
                             capture_output=True, text=True, cwd=cwd, timeout=600)
    return out.stdout


def parse(raw: str) -> Dict[str, Dict[str, Any]]:
    found = {}
    for line in raw.splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if "id" in obj:
            found[str(obj["id"])] = obj
    return found


def fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace("ヶ", "ケ").replace("ヵ", "ケ").replace(" ", "").replace("　", "")


def map_free(pref: str, muni: str, by_code: Dict[str, Any]) -> Optional[str]:
    """MIC code of a named municipality, or None when the name names none."""
    pref_f, muni_f = fold(pref), fold(muni)
    for lg, m in by_code.items():
        if fold(m.prefecture_name) != pref_f:
            continue
        if muni_f in (fold(m.name), fold((m.county or "") + m.name)):
            return lg
    return None


def run_batch(mode: str, items: List[Dict[str, Any]], model: str, by_code: Dict[str, Any]) -> List[Dict[str, Any]]:
    prompt = prompt_for(mode, items, by_code)
    raw = ""
    answers: Dict[str, Dict[str, Any]] = {}
    for _attempt in range(2):
        try:
            raw = call_model(prompt, model)
        except subprocess.TimeoutExpired:
            continue
        answers = parse(raw)
        if len(answers) >= len(items) - 1:
            break
    out = []
    for it in items:
        a = answers.get(str(it["id"]))
        rec: Dict[str, Any] = {"id": it["id"], "raw": a, "lg_code": None, "invented": False}
        if a is not None and mode == "choose":
            try:
                k = int(a.get("choice", 0))
            except (TypeError, ValueError):
                k = 0
            if 1 <= k <= len(it["candidates"]):
                rec["lg_code"] = it["candidates"][k - 1]
        elif a is not None:
            pref, muni = str(a.get("prefecture") or ""), str(a.get("municipality") or "")
            if muni:
                rec["lg_code"] = map_free(pref, muni, by_code)
                rec["invented"] = rec["lg_code"] is None
        rec["confidence"] = (a or {}).get("confidence")
        out.append(rec)
    return [dict(r, prompt_chars=len(prompt), raw_text=raw if i == 0 else None) for i, r in enumerate(out)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["choose", "free"])
    ap.add_argument("items", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    from jaden.data.loader import get_registry
    by_code = {m.lg_code: m for m in get_registry().list_municipalities()}
    items = [json.loads(line) for line in open(args.items, encoding="utf-8")]
    batches = [items[i:i + BATCH] for i in range(0, len(items), BATCH)]
    done = 0
    with open(args.out, "w", encoding="utf-8") as fh, ThreadPoolExecutor(args.jobs) as pool:
        for recs in pool.map(lambda b: run_batch(args.mode, b, args.model, by_code), batches):
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            done += len(recs)
            print(f"  {done:,} / {len(items):,}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
