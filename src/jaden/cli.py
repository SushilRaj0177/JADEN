"""JADEN: High-performance Command-Line Interface.

Supports:
- Interactive single address normalization
- Batch processing of line-delimited files or stdin streams
- JSON / JSONL / CSV / Canonical text output formats
"""

import sys
import argparse
import json
from typing import Optional

# Ensure UTF-8 I/O encoding on Windows platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

from . import __version__, normalize


def main(args: Optional[list[str]] = None) -> int:
    """CLI entry point for JADEN."""
    parser = argparse.ArgumentParser(
        prog="jaden",
        description="JADEN: Japanese Address Data Engineering & Normalization Engine",
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="Japanese address string to normalize. If omitted, reads from stdin.",
    )
    parser.add_argument(
        "-f", "--file",
        help="Path to file containing addresses (one per line).",
    )
    parser.add_argument(
        "-c", "--canonical-only",
        action="store_true",
        help="Output only the canonical normalized address string.",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Output streaming JSON Lines format (for batch pipelines).",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"JADEN {__version__}",
    )

    parsed = parser.parse_args(args)

    # Mode 1: Single address via argument
    if parsed.address:
        result = normalize(parsed.address)
        if parsed.canonical_only:
            print(result.canonical)
        elif parsed.jsonl:
            print(result.to_json())
        else:
            print(result.to_json(indent=2))
        return 0

    # Mode 2: Batch processing via file or stdin
    input_stream = open(parsed.file, "r", encoding="utf-8") if parsed.file else sys.stdin

    try:
        for line in input_stream:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            res = normalize(line_str)
            if parsed.canonical_only:
                print(res.canonical)
            else:
                print(res.to_json())
    finally:
        if parsed.file and input_stream is not sys.stdin:
            input_stream.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
