"""Shared pieces of the real-data evaluations: the worker pool, outcome classes, sampling, tables."""

import hashlib
import heapq
import math
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

DEFAULT_DATA = Path.home() / ".cache" / "jaden-realdata"
ENGINE: Any = None


def init_worker() -> None:
    global ENGINE
    from jaden.engine import AddressNormalizer
    ENGINE = AddressNormalizer()
    ENGINE.normalize("東京都港区芝公園4-2-8")  # load the data once per worker


def resolve(address: str) -> Tuple[Any, Any]:
    """(NormalizedAddress, ValidationResult) of one address."""
    if ENGINE is None:
        init_worker()
    return ENGINE.normalize(address), ENGINE.validate(address)


_BY_CODE5: Optional[Dict[str, Any]] = None


def _municipalities() -> Dict[str, Any]:
    """Current municipalities by their five-digit code."""
    global _BY_CODE5
    if _BY_CODE5 is None:
        if ENGINE is None:
            init_worker()
        _BY_CODE5 = {m.lg_code[:5]: m for m in ENGINE.registry._municipalities_by_code.values()}
    return _BY_CODE5


def municipality_outcome(res: Any, val: Any, truth_lg5: str) -> str:
    """How the municipality answer compares with the dataset's own municipality code.

    A designated city has one code for the city and one per ward. When the row carries the city
    code and JADEN names a ward of that city, the answer is more specific, not different; when the
    row carries a ward code and JADEN stops at the city, the ward is missing.
    """
    lg = res.components.lg_code
    if val.status == "ACCEPTED":
        if lg and lg[:5] == truth_lg5:
            return "correct"
        known = _municipalities()
        truth, mine = known.get(truth_lg5), known.get(lg[:5]) if lg else None
        if truth is None:
            return "row carries a municipality code that no longer exists"
        if mine is not None and mine.city == truth.city and mine.prefecture_code == truth.prefecture_code:
            if truth.entity_type == "designated_city" and mine.ward:
                return "correct (ward found; the row has only the city code)"
            if mine.entity_type == "designated_city" and truth.ward:
                return "city only: the ward was not resolved"
        return "wrong"
    if val.status == "AMBIGUOUS":
        listed = any(f"({truth_lg5}" in cand for cand in val.ambiguous_candidates)
        return "ambiguous, truth listed" if listed else "ambiguous, truth not listed"
    return "rejected: " + val.status


def is_correct(outcome: str) -> bool:
    return outcome.startswith("correct")


def sample_key(ident: str) -> str:
    """Stable pseudo-random order, so examples are spread over the country instead of file order."""
    return hashlib.md5(ident.encode("utf-8")).hexdigest()


class Tally:
    """Counts per (group, outcome) and keeps the ``keep`` examples with the smallest sample key per pair."""

    def __init__(self, keep: int = 40) -> None:
        self.keep = keep
        self.counts: Counter = Counter()
        self.examples: Dict[Tuple[str, str], List[Tuple[str, Any]]] = {}

    def add(self, group: str, outcome: str, ident: str = "", example: Any = None) -> None:
        self.counts[(group, outcome)] += 1
        if example is not None:
            bucket = self.examples.setdefault((group, outcome), [])
            bucket.append((sample_key(ident), example))
            if len(bucket) > 4 * self.keep:
                self.examples[(group, outcome)] = heapq.nsmallest(self.keep, bucket, key=lambda e: e[0])

    def merge(self, other: "Tally") -> None:
        self.counts.update(other.counts)
        for key, bucket in other.examples.items():
            mine = self.examples.setdefault(key, [])
            mine.extend(bucket)
            self.examples[key] = heapq.nsmallest(self.keep, mine, key=lambda e: e[0])

    def trimmed(self) -> "Tally":
        for key, bucket in self.examples.items():
            self.examples[key] = heapq.nsmallest(self.keep, bucket, key=lambda e: e[0])
        return self

    def group(self, group: str) -> Dict[str, int]:
        return {o: n for (g, o), n in sorted(self.counts.items(), key=lambda kv: -kv[1]) if g == group}

    def total(self, group: str) -> int:
        return sum(self.group(group).values())

    def get(self, group: str, outcome: str) -> int:
        return self.counts.get((group, outcome), 0)

    def sample(self, group: str, outcome: str, n: int) -> List[Any]:
        return [e for _, e in heapq.nsmallest(n, self.examples.get((group, outcome), []), key=lambda e: e[0])]


def chunks(items: Iterable[Any], size: int) -> Iterator[List[Any]]:
    batch: List[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def run_pool(worker: Callable[[List[Any]], Tuple[Tally, Any]], items: Iterable[Any], jobs: int,
             chunk_size: int = 4000, on_extra: Optional[Callable[[Any], None]] = None,
             label: str = "") -> Tuple[Tally, int, float]:
    """Runs ``worker`` over chunks of ``items``; returns the merged tally, the item count and the seconds."""
    tally = Tally()
    done = 0
    start = time.perf_counter()
    last = start

    def take(result: Tuple[Tally, Any, int]) -> None:
        nonlocal done, last
        part, extra, n = result
        tally.merge(part)
        if on_extra is not None and extra is not None:
            on_extra(extra)
        done += n
        now = time.perf_counter()
        if now - last > 30:
            last = now
            print(f"  {label}{done:,} addresses, {done / (now - start):,.0f}/s", file=sys.stderr, flush=True)

    if jobs <= 1:
        init_worker()
        for batch in chunks(items, chunk_size):
            take(_call(worker, batch))
    else:
        with Pool(jobs, initializer=init_worker) as pool:
            for result in pool.imap_unordered(_Runner(worker), chunks(items, chunk_size)):
                take(result)
    return tally, done, time.perf_counter() - start


def _call(worker: Callable[[List[Any]], Tuple[Tally, Any]], batch: List[Any]) -> Tuple[Tally, Any, int]:
    part, extra = worker(batch)
    return part.trimmed(), extra, len(batch)


class _Runner:
    def __init__(self, worker: Callable[[List[Any]], Tuple[Tally, Any]]) -> None:
        self.worker = worker

    def __call__(self, batch: List[Any]) -> Tuple[Tally, Any, int]:
        return _call(self.worker, batch)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(a))


def pct(n: int, total: int, digits: int = 2) -> str:
    return f"{100 * n / total:.{digits}f}%" if total else "–"


def table(header: Sequence[str], rows: Iterable[Sequence[Any]], align: Optional[str] = None) -> str:
    align = align or "l" + "r" * (len(header) - 1)
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join(":---" if a == "l" else "---:" for a in align) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def outcome_table(tally: Tally, group: str) -> str:
    total = tally.total(group)
    rows = [(o, f"{n:,}", pct(n, total)) for o, n in tally.group(group).items()]
    return table(("Outcome", "Addresses", "Share"), rows + [("**all**", f"{total:,}", "")])
