"""JADEN: Batch processing of address files.

Reads CSV, TSV, JSONL or plain text (one address per line), resolves the address
column of every row, and writes the rows back with JADEN's result columns appended.
Japanese spreadsheets are often saved as Shift_JIS (cp932); the input encoding is
detected (UTF-8 with or without BOM, then cp932) unless given.

    jaden batch customers.csv --column 住所 -o customers_checked.csv
    jaden batch addresses.txt -o out.jsonl --jobs 4
"""

import contextlib
import csv
import io
import json
import sys
import time
from collections import Counter
import multiprocessing
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, TextIO, Tuple

from .models.address import NormalizedAddress
from .models.validation import ValidationResult
from .core.text import load_json

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


RESOLVE_FIELDS: Tuple[str, ...] = ("resolved_lg_code", "resolved_name", "resolved_probability", "resolved_candidates")

_ENGINE: Any = None
_STRICT = False
_RESOLVE = False


def _init_worker(strict: bool, autocorrect: bool = False, resolve: bool = False) -> None:
    global _ENGINE, _STRICT, _RESOLVE
    from .engine import AddressNormalizer
    _ENGINE = AddressNormalizer(autocorrect=autocorrect)
    _STRICT = strict
    _RESOLVE = resolve


def resolve_record(address: str, side: str = "") -> Dict[str, Any]:
    """The calibrated resolver's verdict as flat columns: the municipality when it clears the 1%-risk
    threshold, its probability, and the five most likely candidates."""
    from .resolve import resolve
    if not (address or "").strip():
        return {k: "" for k in RESOLVE_FIELDS}
    r = resolve(address, side)
    return {
        "resolved_lg_code": r.lg_code if r.answered else "",
        "resolved_name": r.name if r.answered else "",
        "resolved_probability": round(r.probability, 4) if r.candidates else "",
        "resolved_candidates": " | ".join(f"{c.name} ({c.lg_code}) {c.probability:.2f}" for c in r.candidates[:5]),
    }


def _process_item(item: Tuple[str, str]) -> Dict[str, Any]:
    rec = process_address(item[0])
    if _RESOLVE:
        rec.update(resolve_record(item[0], item[1]))
    return rec


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
    # UTF-16 without a byte-order mark: the zero bytes of ASCII (digits, newlines) sit at odd offsets in
    # little-endian text and at even offsets in big-endian text, wherever the first character is kanji
    zeros_odd, zeros_even = raw[1::2].count(0), raw[0::2].count(0)
    if len(raw) >= 4 and len(raw) % 2 == 0 and max(zeros_odd, zeros_even) >= max(2, len(raw) // 16) \
            and min(zeros_odd, zeros_even) * 4 < max(zeros_odd, zeros_even):
        return raw.decode("utf-16-le" if zeros_odd > zeros_even else "utf-16-be", errors="replace")
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
    return {".csv": "csv", ".tsv": "tsv", ".tab": "tsv", ".jsonl": "jsonl", ".ndjson": "jsonl",
            ".xlsx": "xlsx"}.get(suffix, "txt")


@contextlib.contextmanager
def _wide_csv_fields() -> Iterator[None]:
    """Lets a CSV cell be longer than Python's default 131,072 characters while JADEN reads a file (the
    setting is global, so it is put back afterwards); any other CSV error becomes a plain message."""
    old = csv.field_size_limit()
    csv.field_size_limit(max(old, 1 << 27))
    try:
        yield
    except csv.Error as exc:
        raise ValueError(f"the file cannot be read as CSV: {exc}") from None
    finally:
        csv.field_size_limit(old)


def _load(input_path: Path, in_fmt: str, encoding: Optional[str], column: Optional[str],
          header_row: Optional[bool]) -> Tuple[List[str], Iterator[Tuple[Any, str]], str]:
    """(header, rows, the format the rows are in). An .xlsx sheet is read as CSV rows."""
    with _wide_csv_fields():
        if in_fmt == "xlsx":
            from .xlsx import read_xlsx
            source: Any = io.BytesIO(sys.stdin.buffer.read()) if str(input_path) == "-" else input_path
            buf = io.StringIO()
            csv.writer(buf).writerows(read_xlsx(source))
            header, rows = read_rows(buf.getvalue(), "csv", column, header_row)
            return header, iter(list(rows)), "csv"
        header, rows = read_rows(read_text(input_path, encoding), in_fmt, column, header_row)
        return header, iter(list(rows)), in_fmt


def _formats(input_path: Path, output: Optional[Path], fmt: Optional[str]) -> Tuple[str, str, bool]:
    """(input format, output format, output to stdout)."""
    in_fmt = detect_format(input_path, fmt)
    to_stdout = output is None or str(output) == "-"
    out_fmt = in_fmt if to_stdout else detect_format(output, None)
    if out_fmt == "txt" or (out_fmt == "xlsx" and to_stdout):
        out_fmt = "csv"
    return in_fmt, out_fmt, to_stdout


def _open_output(output: Optional[Path], out_fmt: str, to_stdout: bool, out_encoding: str) -> Tuple[TextIO, str, Any]:
    """(text stream to write rows to, the format to write them in, a function that finishes the file)."""
    import codecs
    try:
        codecs.lookup(out_encoding)
    except LookupError:
        raise ValueError(f"unknown output encoding '{out_encoding}'") from None
    if to_stdout or output is None:
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None and codecs.lookup(out_encoding).name != codecs.lookup(sys.stdout.encoding or "utf-8").name:
            sys.stdout.flush()
            reconfigure(encoding=out_encoding, errors="replace")     # '--output-encoding cp932 > out.csv'
        return sys.stdout, out_fmt, lambda: None
    if out_fmt == "xlsx":
        from .xlsx import write_xlsx
        buf = io.StringIO()

        def finish() -> None:
            with _wide_csv_fields():
                write_xlsx(output, list(csv.reader(io.StringIO(buf.getvalue()))))
        return buf, "csv", finish
    # A character the chosen encoding cannot hold (an emoji in cp932) becomes '?' instead of an error
    stream = open(output, "w", encoding=out_encoding, errors="replace", newline="")
    return stream, out_fmt, stream.close


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
                # A blank row stays (as EMPTY), so the output rows line up with the input's
                yield list(values), (values[index] if index < len(values) else "")
        return header, gen_csv()

    if fmt == "jsonl":
        key = column or "address"

        def gen_jsonl() -> Iterator[Tuple[Row, str]]:
            for number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    yield {}, ""                 # kept, so the output lines up with the input
                    continue
                try:
                    obj = load_json(line)
                except (ValueError, RecursionError) as exc:   # '[[[[…' nested beyond Python's limit
                    raise ValueError(f"line {number}: not valid JSON ({type(exc).__name__})") from None
                if not isinstance(obj, dict):
                    raise ValueError(f"line {number}: expected a JSON object with an '{key}' field")
                yield obj, as_text(obj.get(key))
        return [], gen_jsonl()

    def gen_txt() -> Iterator[Tuple[Row, str]]:
        for line in text.splitlines():
            yield [line.strip()], line.strip()      # a blank line stays, as EMPTY
    return ["address"], gen_txt()


def _cell(value: Any) -> Any:
    """A JSON value as a spreadsheet cell: nested objects and lists as JSON text, null as empty."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _named(header: Sequence[str], values: Sequence[Any]) -> Dict[str, Any]:
    """A CSV row as an object with nothing lost: a repeated column name gets '_2', '_3'; values beyond the
    header get 'column4', 'column5' (counted from 1)."""
    out: Dict[str, Any] = {}
    for i, value in enumerate(values):
        name = header[i] if i < len(header) and header[i] else f"column{i + 1}"
        key, n = name, 1
        while key in out:
            n += 1
            key = f"{name}_{n}"
        out[key] = value
    return out


def _widened(header: List[str], rows: Sequence[Tuple[Row, str]]) -> List[str]:
    """The header with 'column4', 'column5', … for values beyond it, so a row longer than the header keeps
    its extra values and the result columns stay in place."""
    width = max((len(row) for row, _ in rows if isinstance(row, list)), default=0)
    return list(header) + [f"column{i + 1}" for i in range(len(header), width)] if header else list(header)


def _union_header(rows: Sequence[Tuple[Row, str]]) -> List[str]:
    """Every key of a file of JSON objects, in the order they first appear (not only the first row's)."""
    names: Dict[str, None] = {}
    for row, _ in rows:
        if isinstance(row, dict):
            names.update(dict.fromkeys(row))
    return list(names)


class _Writer:
    """Writes input rows with result columns appended, by position for CSV / TSV (nothing overwritten)."""

    def __init__(self, stream: TextIO, out_fmt: str, header: List[str], result_names: List[str], log: TextIO) -> None:
        self.stream, self.out_fmt, self.header, self.result_names = stream, out_fmt, header, result_names
        self.writer: Any = None
        clash = sorted(set(header) & set(result_names))
        if clash and out_fmt != "jsonl":
            log.write(f"warning: the input already has column(s) {', '.join(clash)}; both are kept, the input's first\n")

    def write(self, row: Row, rec: Dict[str, Any]) -> None:
        from .core.text import encodable
        if isinstance(row, dict):
            row = {k: (encodable(v) if isinstance(v, str) else v) for k, v in row.items()}
        else:
            row = [encodable(v) if isinstance(v, str) else v for v in row]
        if self.out_fmt == "jsonl":
            base = row if isinstance(row, dict) else {"address": row[0]} if len(row) == 1 and not self.header \
                else _named(self.header, row)
            self.stream.write(json.dumps({**base, "jaden": rec}, ensure_ascii=False) + "\n")
            return
        if self.writer is None:
            self.writer = csv.writer(self.stream, delimiter="," if self.out_fmt == "csv" else "\t")
            names = self.header if self.header else (list(row.keys()) if isinstance(row, dict) else [])
            self.header = names
            self.writer.writerow(names + self.result_names)
        if isinstance(row, dict):
            values = [_cell(row.get(n)) for n in self.header]
        else:
            values = list(row) + [""] * (len(self.header) - len(row))
        self.writer.writerow(values + [("" if v is None else v) for v in rec.values()])


def _side_reader(header: Sequence[str], fmt: str, name_column: Optional[str]) -> Any:
    """A function giving the side-information text (a company or facility name) of a row."""
    from .core.text import as_text
    if not name_column:
        return lambda row: ""
    if fmt == "jsonl":
        return lambda row: as_text(row.get(name_column)) if isinstance(row, dict) else ""
    if fmt == "txt":
        raise ValueError("--name-column needs a CSV, TSV or JSONL file")
    index = _column_index(header, name_column)
    return lambda row: row[index] if index < len(row) else ""


def run_batch(input_path: Path, output: Optional[Path], fmt: Optional[str] = None, column: Optional[str] = None,
              encoding: Optional[str] = None, out_encoding: str = "utf-8", strict: bool = False, jobs: int = 1,
              prefix: str = "jaden_", log: TextIO = sys.stderr, autocorrect: bool = False,
              header_row: Optional[bool] = None, resolve: bool = False, name_column: Optional[str] = None) -> Counter:
    """Processes a file and writes the rows with result columns appended; returns counts by status.
    ``resolve`` adds the calibrated resolver's columns; ``name_column`` names the column holding a company
    or facility name to use as evidence."""
    in_fmt, out_fmt, to_stdout = _formats(input_path, output, fmt)
    header, rows, in_fmt = _load(input_path, in_fmt, encoding, column, header_row)
    materialized = list(rows)
    if in_fmt == "jsonl":
        header = _union_header(materialized)
    else:
        header = _widened(header, materialized)
    side_of = _side_reader(header, in_fmt, name_column)

    out_stream, out_fmt, finish = _open_output(output, out_fmt, to_stdout, out_encoding)
    counts: Counter = Counter()
    started = time.perf_counter()
    pool = None
    fields = RESULT_FIELDS + (RESOLVE_FIELDS if resolve else ())
    writer = _Writer(out_stream, out_fmt, header, [prefix + k for k in fields], log)
    try:
        items = [(a, side_of(row)) for row, a in materialized]
        results: Iterable[Dict[str, Any]]
        if jobs > 1 and len(items) > 1:
            # 'spawn': forking a process that already runs threads (the data loaders') can deadlock the child
            pool = multiprocessing.get_context("spawn").Pool(jobs, initializer=_init_worker,
                                                             initargs=(strict, autocorrect, resolve))
            results = pool.imap(_process_item, items, chunksize=256)
        else:
            _init_worker(strict, autocorrect, resolve)
            results = map(_process_item, items)
        for (row, _), rec in zip(materialized, results):
            counts[rec["status"]] += 1
            writer.write(row, rec)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
        finish()
    elapsed = time.perf_counter() - started
    total = sum(counts.values())
    summary = ", ".join(f"{k} {v}" for k, v in counts.most_common())
    rate = f"{total / elapsed:,.0f}/s" if elapsed > 0 else "-"
    log.write(f"{total} rows in {elapsed:.1f}s ({rate}): {summary}\n")
    if total >= 10 and counts["MALFORMED"] + counts["EMPTY"] >= 0.8 * total:
        log.write("warning: most rows were rejected or empty; check --column and --encoding\n")
    return counts


AUDIT_FIELDS = ("audit", "code_status", "resolved_code", "suggested_code", "candidates", "former_name",
                "municipality_written", "audit_detail")


def run_audit(input_path: Path, output: Optional[Path], code_column: str, fmt: Optional[str] = None,
              column: Optional[str] = None, encoding: Optional[str] = None, out_encoding: str = "utf-8",
              prefix: str = "jaden_", log: TextIO = sys.stderr, header_row: Optional[bool] = None) -> Counter:
    """Checks every row's address against the municipality code in ``code_column`` (see jaden.audit) and
    writes the rows back with the verdict columns appended; returns counts by verdict."""
    from .audit import check_record
    in_fmt, out_fmt, to_stdout = _formats(input_path, output, fmt)
    header, rows, in_fmt = _load(input_path, in_fmt, encoding, column, header_row)
    materialized = list(rows)
    if in_fmt == "jsonl":
        header = _union_header(materialized)
    else:
        header = _widened(header, materialized)
    code_of = _side_reader(header, in_fmt, code_column)
    counts: Counter = Counter()
    out_stream, out_fmt, finish = _open_output(output, out_fmt, to_stdout, out_encoding)
    try:
        writer = _Writer(out_stream, out_fmt, header, [prefix + k for k in AUDIT_FIELDS], log)
        for row, address in materialized:
            r = check_record((address or "").strip(), str(code_of(row) or "").strip() or None)
            counts[r.verdict] += 1
            writer.write(row, {"audit": r.verdict, "code_status": r.code_status, "resolved_code": r.resolved_code,
                               "suggested_code": r.suggested_code, "candidates": " ".join(r.candidates[:20]),
                               "former_name": r.former_name, "municipality_written": r.municipality_written,
                               "audit_detail": r.detail})
    finally:
        finish()
    log.write(f"{sum(counts.values())} rows: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()) + "\n")
    return counts


def run_dedupe(input_path: Path, output: Optional[Path], fmt: Optional[str] = None, column: Optional[str] = None,
               encoding: Optional[str] = None, out_encoding: str = "utf-8", level: str = "unit",
               prefix: str = "jaden_", log: TextIO = sys.stderr, header_row: Optional[bool] = None,
               pairs: Optional[Path] = None, min_score: float = 0.5) -> Dict[str, int]:
    """Groups the rows of a file by address (名寄せ) and writes them back with group columns.

    Appended columns: status, canonical, match_key, group (same number = same address at
    ``level``), group_size. Rows whose address cannot be keyed keep an empty group.
    ``pairs``: also write a CSV of likely duplicate pairs (rows on the same block) with a score
    and the reasons, including near-matches the groups leave apart (a typo in the building name,
    a room on one side only).
    """
    from .engine import get_engine
    from .matching import match_key

    in_fmt, out_fmt, to_stdout = _formats(input_path, output, fmt)
    header, rows, in_fmt = _load(input_path, in_fmt, encoding, column, header_row)
    materialized = list(rows)
    if in_fmt == "jsonl":
        header = _union_header(materialized)
    else:
        header = _widened(header, materialized)
    engine = get_engine()

    records: List[Dict[str, Any]] = []
    groups: Dict[str, int] = {}
    sizes: Counter = Counter()
    resolved: List[Tuple[int, Any]] = []
    for row_number, (_, address) in enumerate(materialized, 1):
        address = (address or "").strip()
        res = engine.normalize(address) if address else None
        if res is not None:
            resolved.append((row_number, res))
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

    out_stream, out_fmt, finish = _open_output(output, out_fmt, to_stdout, out_encoding)
    try:
        names = [prefix + k for k in ("status", "canonical", "match_key", "group", "group_size")]
        writer = _Writer(out_stream, out_fmt, header, names, log)
        for (row, _), rec in zip(materialized, records):
            writer.write(row, rec)
    finally:
        finish()

    if pairs is not None:
        from .matching import duplicate_pairs
        report: Dict[str, Any] = {}
        found = duplicate_pairs([r for _, r in resolved], min_score=min_score, report=report)
        if report.get("truncated"):
            log.write(f"warning: stopped after {report['comparisons']:,} comparisons; some pairs may be missing\n")
        with open(pairs, "w", encoding=out_encoding, newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_a", "row_b", "score", "verdict", "address_a", "address_b", "reasons"])
            for pair in found:
                (ra, a), (rb, b) = resolved[pair.i], resolved[pair.j]
                w.writerow([ra, rb, pair.score, pair.verdict, a.input_raw, b.input_raw, "; ".join(pair.reasons)])
        log.write(f"{len(found)} likely duplicate pairs written to {pairs}\n")

    duplicate_groups = sum(1 for n in sizes.values() if n > 1)
    duplicate_rows = sum(n for n in sizes.values() if n > 1)
    unkeyed = sum(1 for r in records if not r["group"])
    summary = {"rows": len(records), "groups": len(sizes), "duplicate_groups": duplicate_groups,
               "rows_in_duplicate_groups": duplicate_rows, "unkeyed_rows": unkeyed}
    log.write(f"{len(records)} rows: {duplicate_groups} duplicate groups covering {duplicate_rows} rows; "
              f"{unkeyed} rows could not be keyed at the {level} level\n")
    return summary
