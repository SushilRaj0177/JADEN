"""JADEN: Batch processing of address files.

Reads CSV, TSV, JSONL or plain text (one address per line), resolves the address
column of every row, and writes the rows back with JADEN's result columns appended.
Japanese spreadsheets are often saved as Shift_JIS (cp932); the input encoding is
detected (UTF-8 with or without BOM, then cp932) unless given.

    jaden batch customers.csv --column 住所 -o customers_checked.csv
    jaden batch addresses.txt -o out.jsonl --jobs 4
"""

import csv
import io
import json
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, TextIO, Tuple

from .models.address import NormalizedAddress
from .models.validation import ValidationResult

RESULT_FIELDS: Tuple[str, ...] = (
    "status", "valid", "canonical", "lg_code", "prefecture", "county", "city", "ward", "town",
    "chome", "ban", "go", "banchi", "edaban", "lot_number", "building", "floor", "unit",
    "postal_code", "kana", "romaji", "latitude", "longitude", "location_level",
    "verification_level", "former_municipality", "candidates", "message",
)


def flat_record(res: NormalizedAddress, val: ValidationResult) -> Dict[str, Any]:
    """One flat, spreadsheet-friendly record of an address result."""
    c = res.components
    return {
        "status": val.status,
        "valid": val.valid,
        "canonical": res.canonical if res.confidence_score > 0 else "",
        "lg_code": c.lg_code,
        "prefecture": c.prefecture,
        "county": c.county,
        "city": c.city,
        "ward": c.ward,
        "town": c.town,
        "chome": c.chome,
        "ban": c.ban,
        "go": c.go,
        "banchi": c.banchi,
        "edaban": c.edaban,
        "lot_number": c.lot_number,
        "building": c.building,
        "floor": c.floor,
        "unit": c.unit,
        "postal_code": c.postal_code,
        "kana": res.kana,
        "romaji": res.romaji,
        "latitude": res.latitude,
        "longitude": res.longitude,
        "location_level": res.location_level,
        "verification_level": val.verification_level,
        "former_municipality": c.former_municipality,
        "candidates": " | ".join(val.ambiguous_candidates),
        "message": "; ".join([val.message] + [w for w in val.warnings if w not in val.message]),
    }


_ENGINE: Any = None
_STRICT = False


def _init_worker(strict: bool) -> None:
    global _ENGINE, _STRICT
    from .engine import AddressNormalizer
    _ENGINE = AddressNormalizer()
    _STRICT = strict


def process_address(address: str) -> Dict[str, Any]:
    """Flat result record for one address (used by the batch command and its workers)."""
    if _ENGINE is None:
        _init_worker(_STRICT)
    address = (address or "").strip()
    if not address:
        empty: Dict[str, Any] = {k: None for k in RESULT_FIELDS}
        empty.update(status="EMPTY", valid=False)
        return empty
    res = _ENGINE.normalize(address)
    val = _ENGINE.validate(address, strict=_STRICT)
    return flat_record(res, val)


def read_text(path: Path, encoding: Optional[str]) -> str:
    raw = sys.stdin.buffer.read() if str(path) == "-" else path.read_bytes()
    if encoding:
        return raw.decode(encoding)
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def detect_format(path: Optional[Path], fmt: Optional[str]) -> str:
    if fmt:
        return fmt
    suffix = path.suffix.lower() if path is not None else ""
    return {".csv": "csv", ".tsv": "tsv", ".tab": "tsv", ".jsonl": "jsonl", ".ndjson": "jsonl"}.get(suffix, "txt")


def _column_index(header: Sequence[str], column: Optional[str]) -> int:
    if column is None:
        for i, name in enumerate(header):
            if name.strip().lower() in ("address", "住所", "所在地", "addr", "full_address"):
                return i
        return 0
    if column.isdigit():
        return int(column) - 1
    if column in header:
        return list(header).index(column)
    raise ValueError(f"column '{column}' not found; columns are: {', '.join(header)}")


def read_rows(text: str, fmt: str, column: Optional[str]) -> Tuple[List[str], Iterator[Tuple[Dict[str, Any], str]]]:
    """(input field names, iterator of (row, address))."""
    if fmt in ("csv", "tsv"):
        reader = csv.reader(io.StringIO(text), delimiter="," if fmt == "csv" else "\t")
        header = next(reader, [])
        index = _column_index(header, column)

        def gen_csv() -> Iterator[Tuple[Dict[str, Any], str]]:
            for values in reader:
                if not any(v.strip() for v in values):
                    continue
                yield dict(zip(header, values)), (values[index] if index < len(values) else "")
        return list(header), gen_csv()

    if fmt == "jsonl":
        key = column or "address"

        def gen_jsonl() -> Iterator[Tuple[Dict[str, Any], str]]:
            for line in text.splitlines():
                if line.strip():
                    obj = json.loads(line)
                    yield obj, str(obj.get(key, ""))
        return [], gen_jsonl()

    def gen_txt() -> Iterator[Tuple[Dict[str, Any], str]]:
        for line in text.splitlines():
            if line.strip():
                yield {"address": line.strip()}, line.strip()
    return ["address"], gen_txt()


def run_batch(input_path: Path, output: Optional[Path], fmt: Optional[str] = None, column: Optional[str] = None,
              encoding: Optional[str] = None, out_encoding: str = "utf-8", strict: bool = False, jobs: int = 1,
              prefix: str = "jaden_", log: TextIO = sys.stderr) -> Counter:
    """Processes a file and writes the rows with result columns appended; returns counts by status."""
    in_fmt = detect_format(input_path, fmt)
    to_stdout = output is None or str(output) == "-"
    out_fmt = in_fmt if to_stdout else detect_format(output, None)
    if out_fmt == "txt":
        out_fmt = "csv"
    header, rows = read_rows(read_text(input_path, encoding), in_fmt, column)
    materialized = list(rows)

    out_stream: TextIO = sys.stdout
    if not to_stdout and output is not None:
        out_stream = open(output, "w", encoding=out_encoding, newline="")
    counts: Counter = Counter()
    started = time.perf_counter()
    pool = None
    try:
        addresses = [a for _, a in materialized]
        results: Iterable[Dict[str, Any]]
        if jobs > 1 and len(addresses) > 1:
            pool = Pool(jobs, initializer=_init_worker, initargs=(strict,))
            results = pool.imap(process_address, addresses, chunksize=256)
        else:
            _init_worker(strict)
            results = map(process_address, addresses)
        writer = None
        for (row, _), rec in zip(materialized, results):
            counts[rec["status"]] += 1
            if out_fmt == "jsonl":
                out_stream.write(json.dumps({**row, "jaden": rec}, ensure_ascii=False) + "\n")
                continue
            if writer is None:
                fields = list(header or row.keys()) + [prefix + k for k in RESULT_FIELDS]
                writer = csv.DictWriter(out_stream, fieldnames=fields, delimiter="," if out_fmt == "csv" else "\t",
                                        extrasaction="ignore")
                writer.writeheader()
            writer.writerow({**row, **{prefix + k: ("" if v is None else v) for k, v in rec.items()}})
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        if out_stream is not sys.stdout:
            out_stream.close()
    elapsed = time.perf_counter() - started
    total = sum(counts.values())
    summary = ", ".join(f"{k} {v}" for k, v in counts.most_common())
    rate = f"{total / elapsed:,.0f}/s" if elapsed > 0 else "-"
    log.write(f"{total} rows in {elapsed:.1f}s ({rate}): {summary}\n")
    return counts
