"""Working with tables: pandas DataFrames, and a line-by-line NDJSON stream.

    >>> import pandas as pd, jaden.frame
    >>> df = pd.DataFrame({"住所": ["港区芝公園4-2-8", "府中市1-1"]})
    >>> out = jaden.frame.normalize_frame(df, "住所")
    >>> out[["住所", "jaden_status", "jaden_canonical"]]

pandas is optional: this module imports it only when a DataFrame function is called.

    $ tail -f orders.ndjson | jaden stream --column address

``jaden stream`` reads one address per line (plain text, a JSON string, or a JSON object holding the
address) and writes one JSON record per line as soon as each is read, so it can sit in a pipeline.
"""

import json
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, TextIO

from .batch import RESOLVE_FIELDS, RESULT_FIELDS, flat_record, resolve_record
from .core.text import as_text, encodable, load_json


_ENGINES: Dict[bool, Any] = {}


def _engine(fix: bool) -> Any:
    """One engine per setting, built once (building one takes a few tens of milliseconds)."""
    if fix not in _ENGINES:
        from .engine import AddressNormalizer
        _ENGINES[fix] = AddressNormalizer(autocorrect=fix)
    return _ENGINES[fix]


def records(addresses: Iterable[Any], strict: bool = False, fix: bool = False, resolve: bool = False,
            names: Optional[Iterable[Any]] = None) -> Iterator[Dict[str, Any]]:
    """One flat record per address (the columns `jaden batch` writes, without the prefix)."""
    engine = _engine(fix)
    side = iter(names) if names is not None else None
    for value in addresses:
        text = as_text(value).strip()
        name = as_text(next(side, "")) if side is not None else ""
        if text:
            res = engine.normalize(text)
            rec = flat_record(res, engine.validate(text, strict=strict, normalized=res))
        else:
            rec = {k: None for k in RESULT_FIELDS}
            rec.update(status="EMPTY", valid=False, reason="EMPTY", message_ja="住所が入力されていません。")
        if resolve:
            rec.update(resolve_record(text, name))
        yield rec


def normalize_series(series: Any, strict: bool = False, fix: bool = False, resolve: bool = False,
                     names: Any = None) -> Any:
    """A DataFrame of results, one row per value of ``series``, on the same index."""
    import pandas as pd  # type: ignore[import-untyped]
    columns = list(RESULT_FIELDS) + (list(RESOLVE_FIELDS) if resolve else [])
    if names is not None and hasattr(names, "reindex"):
        names = names.reindex(series.index)          # names go with the rows they belong to, by index
    rows: List[Dict[str, Any]] = list(records(series, strict=strict, fix=fix, resolve=resolve, names=names))
    return pd.DataFrame(rows, index=series.index, columns=columns)


def normalize_frame(df: Any, column: str = "address", prefix: str = "jaden_", strict: bool = False,
                    fix: bool = False, resolve: bool = False, name_column: Optional[str] = None) -> Any:
    """A copy of ``df`` with the result columns appended (``prefix`` + name)."""
    import pandas as pd
    if column not in df.columns:
        raise KeyError(f"column '{column}' not found; columns are: {', '.join(map(str, df.columns))}")
    if name_column and name_column not in df.columns:
        raise KeyError(f"column '{name_column}' not found")
    names = df[name_column] if name_column else None
    results = normalize_series(df[column], strict=strict, fix=fix, resolve=resolve, names=names).add_prefix(prefix)
    # Running it again replaces the earlier result columns instead of adding a second set
    return pd.concat([df.drop(columns=[c for c in results.columns if c in df.columns]), results], axis=1)


def _address_of(line: str, column: str) -> Optional[Dict[str, Any]]:
    """(the input object, the address) for one stream line; a blank line is an empty address, so the
    output keeps one line per input line."""
    line = line.strip()
    if not line:
        return {"input": "", "address": ""}
    if line[0] in "{\"[":
        try:
            value = load_json(line)
        except (ValueError, RecursionError):   # nested beyond Python's limit: kept as text
            return {"input": line, "address": line}
        if isinstance(value, dict):
            return {"input": value, "address": as_text(value.get(column))}
        if isinstance(value, str):
            return {"input": value, "address": value}
        return {"input": value, "address": "", "error": "expected an address or a JSON object"}
    return {"input": line, "address": line}


def stream(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout, column: str = "address", strict: bool = False,
           fix: bool = False, resolve: bool = False, name_column: Optional[str] = None) -> int:
    """Reads lines until the input ends and writes one JSON record per line, flushing each."""
    engine = _engine(fix)
    count = 0
    for line in stdin:
        item = _address_of(line, column)
        if item is None:
            continue
        text = item["address"].strip()
        out: Dict[str, Any] = {"input": item["input"]}
        if "error" in item:
            out["error"] = item["error"]
        elif not text:
            out["jaden"] = {"status": "EMPTY", "valid": False, "reason": "EMPTY"}
        else:
            res = engine.normalize(text)
            out["jaden"] = flat_record(res, engine.validate(text, strict=strict, normalized=res))
            if resolve:
                side = item["input"].get(name_column) if name_column and isinstance(item["input"], dict) else ""
                out["jaden"].update(resolve_record(text, as_text(side)))
        stdout.write(encodable(json.dumps(out, ensure_ascii=False)) + "\n")
        stdout.flush()
        count += 1
    return count
