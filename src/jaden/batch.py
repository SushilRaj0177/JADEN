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
    "status", "valid", "canonical", "hyphenated", "precision", "lg_code", "prefecture", "county", "city", "ward", "town",
    "chome", "ban", "go", "banchi", "edaban", "lot_number", "building", "floor", "unit",
    "postal_code", "kana", "romaji", "latitude", "longitude", "location_level",
    "verification_level", "former_municipality", "corrected_from", "suggestions", "candidates", "message",
    "reason", "message_ja",
)


def flat_record(res: NormalizedAddress, val: ValidationResult) -> Dict[str, Any]:
    """One flat, spreadsheet-friendly record of an address result."""
    c = res.components
    return {
        "status": val.status,
        "valid": val.valid,
        "canonical": res.canonical if res.confidence_score > 0 else "",
        "hyphenated": res.format("hyphen") if res.confidence_score > 0 else "",
        "precision": val.precision,
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
        "corrected_from": c.town_corrected_from,
        "suggestions": " | ".join(res.suggestions),
        "candidates": " | ".join(val.ambiguous_candidates),
        "message": "; ".join([val.message] + [w for w in val.warnings if w not in val.message]),
        "reason": val.reason,
        "message_ja": val.message_ja,
    }


_ENGINE: Any = None
_STRICT = False


def _init_worker(strict: bool, autocorrect: bool = False) -> None:
    global _ENGINE, _STRICT
    from .engine import AddressNormalizer
    _ENGINE = AddressNormalizer(autocorrect=autocorrect)
    _STRICT = strict


def process_address(address: str) -> Dict[str, Any]:
    """Flat result record for one address (used by the batch command and its workers)."""
    if _ENGINE is None:
        _init_worker(_STRICT)
    address = (address or "").strip()
    if not address:
        empty: Dict[str, Any] = {k: None for k in RESULT_FIELDS}
        empty.update(status="EMPTY", valid=False, reason="EMPTY", message_ja="住所が入力されていません。")
        return empty
    res = _ENGINE.normalize(address)
    val = _ENGINE.validate(address, strict=_STRICT, normalized=res)
    return flat_record(res, val)


def _japanese_score(text: str) -> int:
    """How Japanese a decoding looks: kana and kanji count, half-width kana and control characters count
    against (EUC-JP bytes read as cp932 come out as half-width kana)."""
    sample = text[:20000]
    good = sum(1 for ch in sample if "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    bad = sum(1 for ch in sample if "\uff61" <= ch <= "\uff9f" or (ch < " " and ch not in "\t\r\n"))
    return good - 3 * bad


def read_text(path: Path, encoding: Optional[str]) -> str:
    """The file's text. Without ``encoding``: UTF-16 by its byte-order mark (or its zero bytes), then whichever of
    UTF-8, Shift_JIS (cp932) and EUC-JP decodes cleanly and looks most like Japanese."""
    import codecs
    raw = sys.stdin.buffer.read() if str(path) == "-" else path.read_bytes()
    if encoding:
        try:
            codecs.lookup(encoding)
        except LookupError:
            raise ValueError(f"unknown encoding '{encoding}'") from None
        return raw.decode(encoding)
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    if len(raw) >= 4 and raw.count(b"\x00") > len(raw) // 4:
        return raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "utf-16-be", errors="replace")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    decoded = []
    for enc in ("cp932", "euc_jp"):
        try:
            decoded.append(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    if decoded:
        return max(decoded, key=_japanese_score)
    return raw.decode("utf-8", errors="replace")


def detect_format(path: Optional[Path], fmt: Optional[str]) -> str:
    if fmt:
        return fmt
    suffix = path.suffix.lower() if path is not None else ""
    return {".csv": "csv", ".tsv": "tsv", ".tab": "tsv", ".jsonl": "jsonl", ".ndjson": "jsonl"}.get(suffix, "txt")


_ADDRESS_HEADERS = ("address", "住所", "所在地", "addr", "full_address")


def _column_index(header: Sequence[str], column: Optional[str]) -> int:
    if column is None:
        for i, name in enumerate(header):
            if name.strip().lower() in _ADDRESS_HEADERS:
                return i
        return 0
    if column.isdigit():
        index = int(column) - 1
        if not 0 <= index < max(1, len(header)):
            raise ValueError(f"column {column} is out of range: the file has {len(header)} column(s) (counted from 1)")
        return index
    if column in header:
        return list(header).index(column)
    raise ValueError(f"column '{column}' not found; columns are: {', '.join(header)}")


def _looks_like_address(value: str) -> bool:
    from .engine import get_engine
    return get_engine().validate(value).status in ("ACCEPTED", "AMBIGUOUS")


Row = Any   # a list of field values (CSV / TSV / text) or a dict (JSONL)


def read_rows(text: str, fmt: str, column: Optional[str],
              header_row: Optional[bool] = None) -> Tuple[List[str], Iterator[Tuple[Row, str]]]:
    """(input field names, iterator of (row, address)). CSV rows are kept as value lists, so columns with the
    same name or more values than names lose nothing. ``header_row`` None means: the first row is a header
    unless its address cell is itself an address."""
    from .core.text import as_text
    if fmt in ("csv", "tsv"):
        reader = csv.reader(io.StringIO(text), delimiter="," if fmt == "csv" else "\t")
        first = next(reader, [])
        index = _column_index(first, column)
        if header_row is None:
            named = column is not None and not column.isdigit()
            known = any(n.strip().lower() in _ADDRESS_HEADERS for n in first)
            header_row = named or known or not (index < len(first) and _looks_like_address(first[index]))
        header = list(first) if header_row else [f"column{i + 1}" for i in range(len(first))]

        def gen_csv() -> Iterator[Tuple[Row, str]]:
            if not header_row:
                yield list(first), (first[index] if index < len(first) else "")
            for values in reader:
                if not any(v.strip() for v in values):
                    continue
                yield list(values), (values[index] if index < len(values) else "")
        return header, gen_csv()

    if fmt == "jsonl":
        key = column or "address"

        def gen_jsonl() -> Iterator[Tuple[Row, str]]:
            for number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError as exc:
                    raise ValueError(f"line {number}: not valid JSON ({exc})") from None
                if not isinstance(obj, dict):
                    raise ValueError(f"line {number}: expected a JSON object with an '{key}' field")
                yield obj, as_text(obj.get(key))
        return [], gen_jsonl()

    def gen_txt() -> Iterator[Tuple[Row, str]]:
        for line in text.splitlines():
            if line.strip():
                yield [line.strip()], line.strip()
    return ["address"], gen_txt()


class _Writer:
    """Writes input rows with result columns appended, by position for CSV / TSV (nothing overwritten)."""

    def __init__(self, stream: TextIO, out_fmt: str, header: List[str], result_names: List[str], log: TextIO) -> None:
        self.stream, self.out_fmt, self.header, self.result_names = stream, out_fmt, header, result_names
        self.writer: Any = None
        clash = sorted(set(header) & set(result_names))
        if clash and out_fmt != "jsonl":
            log.write(f"warning: the input already has column(s) {', '.join(clash)}; both are kept, the input's first\n")

    def write(self, row: Row, rec: Dict[str, Any]) -> None:
        if self.out_fmt == "jsonl":
            base = row if isinstance(row, dict) else {"address": row[0]} if len(row) == 1 else dict(zip(self.header, row))
            self.stream.write(json.dumps({**base, "jaden": rec}, ensure_ascii=False) + "\n")
            return
        if self.writer is None:
            self.writer = csv.writer(self.stream, delimiter="," if self.out_fmt == "csv" else "\t")
            names = self.header if self.header else (list(row.keys()) if isinstance(row, dict) else [])
            self.header = names
            self.writer.writerow(names + self.result_names)
        if isinstance(row, dict):
            values = [("" if row.get(n) is None else row.get(n)) for n in self.header]
        else:
            values = list(row) + [""] * (len(self.header) - len(row))
        self.writer.writerow(values + [("" if v is None else v) for v in rec.values()])


def run_batch(input_path: Path, output: Optional[Path], fmt: Optional[str] = None, column: Optional[str] = None,
              encoding: Optional[str] = None, out_encoding: str = "utf-8", strict: bool = False, jobs: int = 1,
              prefix: str = "jaden_", log: TextIO = sys.stderr, autocorrect: bool = False,
              header_row: Optional[bool] = None) -> Counter:
    """Processes a file and writes the rows with result columns appended; returns counts by status."""
    in_fmt = detect_format(input_path, fmt)
    to_stdout = output is None or str(output) == "-"
    out_fmt = in_fmt if to_stdout else detect_format(output, None)
    if out_fmt == "txt":
        out_fmt = "csv"
    header, rows = read_rows(read_text(input_path, encoding), in_fmt, column, header_row)
    materialized = list(rows)

    out_stream: TextIO = sys.stdout
    if not to_stdout and output is not None:
        out_stream = open(output, "w", encoding=out_encoding, newline="")
    counts: Counter = Counter()
    started = time.perf_counter()
    pool = None
    writer = _Writer(out_stream, out_fmt, header, [prefix + k for k in RESULT_FIELDS], log)
    try:
        addresses = [a for _, a in materialized]
        results: Iterable[Dict[str, Any]]
        if jobs > 1 and len(addresses) > 1:
            pool = Pool(jobs, initializer=_init_worker, initargs=(strict, autocorrect))
            results = pool.imap(process_address, addresses, chunksize=256)
        else:
            _init_worker(strict, autocorrect)
            results = map(process_address, addresses)
        for (row, _), rec in zip(materialized, results):
            counts[rec["status"]] += 1
            writer.write(row, rec)
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
    if total >= 10 and counts["MALFORMED"] + counts["EMPTY"] >= 0.8 * total:
        log.write("warning: most rows were rejected or empty; check --column and --encoding\n")
    return counts


def run_dedupe(input_path: Path, output: Optional[Path], fmt: Optional[str] = None, column: Optional[str] = None,
               encoding: Optional[str] = None, out_encoding: str = "utf-8", level: str = "unit",
               prefix: str = "jaden_", log: TextIO = sys.stderr, header_row: Optional[bool] = None) -> Dict[str, int]:
    """Groups the rows of a file by address (名寄せ) and writes them back with group columns.

    Appended columns: status, canonical, match_key, group (same number = same address at
    ``level``), group_size. Rows whose address cannot be keyed keep an empty group.
    """
    from .engine import get_engine
    from .matching import match_key

    in_fmt = detect_format(input_path, fmt)
    to_stdout = output is None or str(output) == "-"
    out_fmt = in_fmt if to_stdout else detect_format(output, None)
    if out_fmt == "txt":
        out_fmt = "csv"
    header, rows = read_rows(read_text(input_path, encoding), in_fmt, column, header_row)
    materialized = list(rows)
    engine = get_engine()

    records: List[Dict[str, Any]] = []
    groups: Dict[str, int] = {}
    sizes: Counter = Counter()
    for _, address in materialized:
        address = (address or "").strip()
        res = engine.normalize(address) if address else None
        val = engine.validate(address, normalized=res) if address else None
        key = match_key(res, level) if res is not None else None
        group = groups.setdefault(key, len(groups) + 1) if key else None
        if group:
            sizes[group] += 1
        records.append({"status": val.status if val else "EMPTY",
                        "canonical": res.canonical if res is not None and res.confidence_score > 0 else "",
                        "match_key": key, "group": group})
    for rec in records:
        rec["group_size"] = sizes[rec["group"]] if rec["group"] else None

    out_stream: TextIO = sys.stdout
    if not to_stdout and output is not None:
        out_stream = open(output, "w", encoding=out_encoding, newline="")
    try:
        names = [prefix + k for k in ("status", "canonical", "match_key", "group", "group_size")]
        writer = _Writer(out_stream, out_fmt, header, names, log)
        for (row, _), rec in zip(materialized, records):
            writer.write(row, rec)
    finally:
        if out_stream is not sys.stdout:
            out_stream.close()

    duplicate_groups = sum(1 for n in sizes.values() if n > 1)
    duplicate_rows = sum(n for n in sizes.values() if n > 1)
    unkeyed = sum(1 for r in records if not r["group"])
    summary = {"rows": len(records), "groups": len(sizes), "duplicate_groups": duplicate_groups,
               "rows_in_duplicate_groups": duplicate_rows, "unkeyed_rows": unkeyed}
    log.write(f"{len(records)} rows: {duplicate_groups} duplicate groups covering {duplicate_rows} rows; "
              f"{unkeyed} rows could not be keyed at the {level} level\n")
    return summary
