"""JADEN: High-performance Command-Line Interface.

Provides clean, professional commands for Japanese address data engineering:
  jaden normalize "<address>" [--json] [-c]
  jaden parse "<address>" [--json]
  jaden validate "<address>" [--json]
"""

import sys
import argparse
import json
from typing import Optional, Sequence, List

# Ensure UTF-8 I/O encoding on Windows platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

from . import __version__, normalize, parse, validate
from .models.address import NormalizedAddress, AddressComponents
from .models.validation import ValidationResult, ValidationStatus


# ==============================================================================
# Terminal Text Formatters (Clean, unadorned, human-readable)
# ==============================================================================

def format_normalize_text(res: NormalizedAddress) -> str:
    """Formats NormalizedAddress for terminal display matching UX specifications."""
    if res.confidence_score == 0.0:
        return (
            f"Input:      {res.input_raw}\n"
            f"Status:     Rejected (unrecognized or malformed address)\n"
            f"Confidence: 0.00\n"
            f"Canonical:  "
        )

    lines: List[str] = []
    c = res.components

    if c.prefecture:
        lines.append(f"Prefecture: {c.prefecture}")
    if c.county:
        lines.append(f"County:     {c.county}")
    if c.city:
        lines.append(f"City:       {c.city}")
    if c.ward:
        lines.append(f"Ward:       {c.ward}")
    if c.town:
        lines.append(f"Town:       {c.town}")
    if c.oaza:
        lines.append(f"Oaza:       {c.oaza}")
    if c.koaza:
        lines.append(f"Koaza:      {c.koaza}")
    if c.kyoto_direction:
        lines.append(f"Kyoto:      {c.kyoto_direction.raw_clause}")
    if c.hokkaido_grid:
        lines.append(f"Hokkaido:   {c.hokkaido_grid.raw_clause}")
    if c.chome is not None:
        lines.append(f"Chome:      {c.chome}")
    if c.ban is not None:
        lines.append(f"Ban:        {c.ban}")
    if c.go is not None:
        lines.append(f"Go:         {c.go}")
    if c.banchi is not None:
        lines.append(f"Banchi:     {c.banchi}")
    if c.edaban is not None:
        lines.append(f"Edaban:     {c.edaban}")
    if c.building:
        lines.append(f"Building:   {c.building}")
    if c.floor:
        lines.append(f"Floor:      {c.floor}")
    if c.unit:
        lines.append(f"Unit:       {c.unit}")

    lines.append(f"Regime:     {c.address_regime}")
    if c.lg_code:
        lines.append(f"LG Code:    {c.lg_code}")
    if c.is_ambiguous:
        candidates_str = ", ".join(c.ambiguous_candidates)
        lines.append(f"Ambiguity:  AMBIGUOUS ({candidates_str})")

    lines.append(f"Confidence: {res.confidence_score:.2f}")
    lines.append(f"Canonical:  {res.canonical}")

    return "\n".join(lines)


def format_parse_text(res: NormalizedAddress) -> str:
    """Formats AddressComponents AST for terminal display."""
    c = res.components
    if res.confidence_score == 0.0:
        return (
            f"Input:        {res.input_raw}\n"
            f"Status:       Rejected (Confidence: 0.00)\n"
            f"Error:        Could not decompose input into Japanese address components."
        )

    sections: List[str] = [f"Input: {res.input_raw}\n"]

    # Administrative
    admin_lines = ["[Administrative]"]
    if c.prefecture:
        pref_str = f"  Prefecture:    {c.prefecture}"
        if c.prefecture_code:
            pref_str += f" (Code: {c.prefecture_code})"
        if c.prefecture_inferred:
            pref_str += " [inferred]"
        admin_lines.append(pref_str)
    if c.county:
        admin_lines.append(f"  County:        {c.county}")
    if c.city:
        admin_lines.append(f"  City:          {c.city}")
    if c.ward:
        admin_lines.append(f"  Ward:          {c.ward}")
    if c.lg_code:
        admin_lines.append(f"  LG Code:       {c.lg_code}")
    if c.town:
        admin_lines.append(f"  Town:          {c.town}")
    if c.oaza:
        admin_lines.append(f"  Oaza:          {c.oaza}")
    if c.koaza:
        admin_lines.append(f"  Koaza:         {c.koaza}")
    sections.append("\n".join(admin_lines))

    # Regional conventions
    if c.kyoto_direction or c.hokkaido_grid:
        reg_lines = ["[Regional Convention]"]
        if c.kyoto_direction:
            reg_lines.append(f"  Thoroughfare:  {c.kyoto_direction.street_1}")
            reg_lines.append(f"  Cross Street:  {c.kyoto_direction.street_2}")
            reg_lines.append(f"  Direction:     {c.kyoto_direction.direction} ({c.kyoto_direction.cardinal})")
        if c.hokkaido_grid:
            reg_lines.append(f"  Hokkaido Grid: {c.hokkaido_grid.raw_clause}")
            reg_lines.append(
                f"  Coordinates:   Jo={c.hokkaido_grid.jo} ({c.hokkaido_grid.cardinal_ns}), "
                f"Chome={c.hokkaido_grid.chome} ({c.hokkaido_grid.cardinal_ew})"
            )
        sections.append("\n".join(reg_lines))

    # Block & Lot
    block_lines = ["[Block & Lot]"]
    if c.chome is not None:
        block_lines.append(f"  Chome:         {c.chome}")
    if c.ban is not None:
        block_lines.append(f"  Ban:           {c.ban}")
    if c.go is not None:
        block_lines.append(f"  Go:            {c.go}")
    if c.banchi is not None:
        block_lines.append(f"  Banchi:        {c.banchi}")
    if c.edaban is not None:
        block_lines.append(f"  Edaban:        {c.edaban}")
    block_lines.append(f"  Regime:        {c.address_regime}")
    sections.append("\n".join(block_lines))

    # Building & Unit
    if c.building or c.floor or c.unit:
        bldg_lines = ["[Building & Unit]"]
        if c.building:
            bldg_lines.append(f"  Building:      {c.building}")
        if c.floor:
            bldg_lines.append(f"  Floor:         {c.floor}")
        if c.unit:
            bldg_lines.append(f"  Unit:          {c.unit}")
        sections.append("\n".join(bldg_lines))

    # Status / Classification
    meta_lines = ["[Classification]"]
    meta_lines.append(f"  Confidence:    {res.confidence_score:.2f}")
    meta_lines.append(f"  Ambiguous:     {c.is_ambiguous}")
    if c.is_ambiguous:
        meta_lines.append(f"  Candidates:    {', '.join(c.ambiguous_candidates)}")
    if c.unparsed_tail:
        meta_lines.append(f"  Unparsed Tail: {c.unparsed_tail}")
    sections.append("\n".join(meta_lines))

    return "\n\n".join(sections)


def format_validate_text(v: ValidationResult) -> str:
    """Formats ValidationResult for terminal display."""
    lines: List[str] = [
        f"Input:       {v.raw_input}",
        f"Status:      {v.status}",
        f"Valid:       {'Yes' if v.valid else 'No'}",
        f"Confidence:  {v.confidence_score:.2f}",
    ]
    if v.lg_code:
        lines.append(f"LG Code:     {v.lg_code}")
    if v.address_regime:
        lines.append(f"Regime:      {v.address_regime}")
    if v.message:
        lines.append(f"Message:     {v.message}")
    if v.ambiguous_candidates:
        lines.append("Candidates:")
        for cand in v.ambiguous_candidates:
            lines.append(f"  • {cand}")

    return "\n".join(lines)


# ==============================================================================
# Command Handlers
# ==============================================================================

def handle_normalize(address: str, as_json: bool, canonical_only: bool) -> int:
    """Executes the normalize command."""
    res = normalize(address)

    if as_json:
        print(res.to_json(indent=2))
    elif canonical_only:
        print(res.canonical)
    else:
        print(format_normalize_text(res))

    return 0 if res.confidence_score > 0.0 else 1


def handle_parse(address: str, as_json: bool) -> int:
    """Executes the parse command."""
    res = normalize(address)

    if as_json:
        output_dict = {
            "raw_input": res.input_raw,
            "components": res.to_dict()["components"],
            "tier_map": res.tier_map,
            "confidence_score": res.confidence_score,
        }
        print(json.dumps(output_dict, ensure_ascii=False, indent=2))
    else:
        print(format_parse_text(res))

    return 0 if res.confidence_score > 0.0 else 1


def handle_validate(address: str, as_json: bool) -> int:
    """Executes the validate command with status-specific exit codes."""
    val = validate(address)

    if as_json:
        print(val.to_json(indent=2))
    else:
        print(format_validate_text(val))

    # Exit code mapping for shell automation:
    # 0 = ACCEPTED
    # 1 = MALFORMED
    # 2 = AMBIGUOUS
    # 3 = UNSUPPORTED
    if val.status == ValidationStatus.ACCEPTED.value:
        return 0
    elif val.status == ValidationStatus.AMBIGUOUS.value:
        return 2
    elif val.status == ValidationStatus.MALFORMED.value:
        return 1
    else:
        return 3


# ==============================================================================
# CLI Entry Point & Argument Parsing
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Builds the top-level argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="jaden",
        description="JADEN: Japanese Address Data Engineering & Normalization Engine",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"JADEN {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Select a JADEN command to execute",
    )

    # 1. normalize
    norm_p = subparsers.add_parser(
        "normalize",
        help="Normalize a Japanese address into canonical structured representation",
        description="Normalizes address strings, unifies Kanji numbers, resolves administrative boundaries, and canonicalizes block notation.",
    )
    norm_p.add_argument(
        "address",
        help="Japanese address string to normalize. Use '-' to read from stdin.",
    )
    norm_p.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format.",
    )
    norm_p.add_argument(
        "-c", "--canonical-only",
        action="store_true",
        help="Output only the canonical normalized address string.",
    )

    # 2. parse
    parse_p = subparsers.add_parser(
        "parse",
        help="Parse a Japanese address into its granular component AST",
        description="Decomposes Japanese addresses into administrative, regional convention, block/lot, and building/unit layers.",
    )
    parse_p.add_argument(
        "address",
        help="Japanese address string to parse into components. Use '-' to read from stdin.",
    )
    parse_p.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format.",
    )

    # 3. validate
    val_p = subparsers.add_parser(
        "validate",
        help="Validate an address against official Japanese statutory registries",
        description="Validates administrative codes and structural integrity (ACCEPTED, AMBIGUOUS, MALFORMED, UNSUPPORTED).",
    )
    val_p.add_argument(
        "address",
        help="Japanese address string to validate. Use '-' to read from stdin.",
    )
    val_p.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format.",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI main entry point."""
    if argv is None:
        raw_args = list(sys.argv[1:])
    else:
        raw_args = list(argv)

    # Pre-parse heuristic: if the first argument is not a known subcommand or flag,
    # default to 'normalize' for convenience and backward compatibility.
    known_cmds = {"normalize", "parse", "validate", "-h", "--help", "-v", "--version"}
    if raw_args and raw_args[0] not in known_cmds and not raw_args[0].startswith("-"):
        raw_args.insert(0, "normalize")

    parser = build_parser()

    # If no arguments provided at all:
    if not raw_args:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(raw_args)
    except SystemExit as exc:
        return exc.code

    if not args.command:
        parser.print_help()
        return 0

    # Resolve address input (from argument or stdin when '-')
    target_address = args.address
    if target_address == "-":
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            target_address = stdin_content
        else:
            sys.stderr.write("Error: Address input from stdin is empty.\n")
            return 2

    try:
        if args.command == "normalize":
            return handle_normalize(target_address, as_json=args.json, canonical_only=args.canonical_only)
        elif args.command == "parse":
            return handle_parse(target_address, as_json=args.json)
        elif args.command == "validate":
            return handle_validate(target_address, as_json=args.json)
        else:
            parser.print_help()
            return 2
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
