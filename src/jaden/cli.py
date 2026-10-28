"""JADEN: High-performance Command-Line Interface.

Provides clean, professional commands for Japanese address data engineering:
  jaden normalize "<address>" [--json] [-c]
  jaden parse "<address>" [--json]
  jaden validate "<address>" [--json]
  jaden geocode "<address>" [--json] [--provider gsi|offline]
  jaden data info | update | fetch-blocks <pref>...
"""

import sys
import argparse
import json
from typing import Optional, Sequence, List, Final, NoReturn

# Standard sysexits codes for CLI errors
EX_USAGE: Final[int] = 64      # Command-line usage error, unknown flag, missing arg, empty stdin
EX_SOFTWARE: Final[int] = 70   # Internal unhandled software crash

# Ensure UTF-8 I/O encoding on Windows platforms
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except Exception:
            pass

from . import __version__, normalize, validate, geocode
from .models.address import NormalizedAddress, AddressComponents
from .models.validation import ValidationResult, ValidationStatus
from .models.geospatial import GeospatialResult, GeocodingStatus


class JadenArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser that exits with EX_USAGE (64) instead of 2 on usage errors."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EX_USAGE, f"{self.prog}: error: {message}\n")

    def exit(self, status: int = 0, message: Optional[str] = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        if status == 2:
            status = EX_USAGE
        raise SystemExit(status)


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
    if c.postal_code:
        lines.append(f"Postal:     〒{c.postal_code}")
    if c.town_verified is not None:
        lines.append(f"Verified:   {_verification_text(c)}")
    if c.is_ambiguous:
        candidates_str = ", ".join(c.ambiguous_candidates)
        lines.append(f"Ambiguity:  AMBIGUOUS ({candidates_str})")

    lines.append(f"Confidence: {res.confidence_score:.2f}")
    lines.append(f"Canonical:  {res.canonical}")
    if res.kana:
        lines.append(f"Kana:       {res.kana}")
    if res.romaji:
        lines.append(f"Romaji:     {res.romaji}")
    if res.latitude is not None and res.longitude is not None:
        lines.append(f"Location:   {res.latitude:.6f}, {res.longitude:.6f} ({res.location_level} level, offline)")
    for note in res.notes:
        lines.append(f"Note:       {note}")

    return "\n".join(lines)


def _verification_text(c: AddressComponents) -> str:
    if c.town_verified is False:
        return "town not found in the national gazetteer"
    parts = ["town"]
    if c.chome_verified is True:
        parts.append("丁目")
    if c.block_verified is True:
        parts.append("block")
    text = " + ".join(parts) + " registered"
    if c.chome_verified is False:
        text += f"; {c.chome}丁目 does not exist"
    return text


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
    if c.machiaza_id:
        admin_lines.append(f"  Machiaza ID:   {c.machiaza_id}")
    if c.postal_code:
        admin_lines.append(f"  Postal Code:   {c.postal_code}")
    if c.municipality_inferred:
        admin_lines.append("  Municipality:  [deduced from town / postal code]")
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
    if c.town_verified is not None:
        meta_lines.append(f"  Gazetteer:     {_verification_text(c)}")
    for note in res.notes:
        meta_lines.append(f"  Note:          {note}")
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
    if v.verification_level != "none":
        lines.append(f"Verified to: {v.verification_level}")
    if v.message:
        lines.append(f"Message:     {v.message}")
    for w in v.warnings:
        lines.append(f"Note:        {w}")
    if v.ambiguous_candidates:
        lines.append(f"Candidates:  {len(v.ambiguous_candidates)}")
        for cand in v.ambiguous_candidates[:15]:
            lines.append(f"  • {cand}")
        if len(v.ambiguous_candidates) > 15:
            lines.append(f"  … and {len(v.ambiguous_candidates) - 15} more (use --json for all)")

    return "\n".join(lines)


def format_geocode_text(res: GeospatialResult) -> str:
    """Formats GeospatialResult for terminal display."""
    lines: List[str] = [
        f"Input:       {res.query}",
        f"Status:      {res.status}",
        f"Provider:    {res.provider}",
    ]
    if res.coordinates:
        lines.append(f"Coordinates: {res.coordinates.latitude:.6f}, {res.coordinates.longitude:.6f} (Lat, Lon)")
    if res.metadata.get("level"):
        lines.append(f"Precision:   {res.metadata['level']}")
    if res.matched_address:
        lines.append(f"Matched:     {res.matched_address}")
    if res.candidates:
        lines.append("Candidates:")
        for cand in res.candidates:
            lines.append(f"  • {cand}")
    if res.error_message:
        lines.append(f"Message:     {res.error_message}")

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


def handle_validate(address: str, as_json: bool, strict: bool = False) -> int:
    """Executes the validate command with status-specific exit codes."""
    val = validate(address, strict=strict)

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


def handle_geocode(address: str, as_json: bool, provider: str = "gsi", timeout: float = 5.0) -> int:
    """Executes the geocode command with resolution exit codes."""
    res = geocode(address, timeout=timeout, provider=provider)

    if as_json:
        print(res.to_json(indent=2))
    else:
        print(format_geocode_text(res))

    return 0 if res.status == GeocodingStatus.SUCCESS.value else 1


def handle_data(action: str, prefectures: Sequence[int], as_json: bool) -> int:
    """Shows, refreshes, or extends the gazetteer data from the official open-data sources."""
    from .data.gazetteer import get_gazetteer, reset_gazetteer, user_data_dir
    from .data import build_gazetteer

    if action == "info":
        gaz = get_gazetteer()
        prov = gaz.provenance()
        blocks = sorted({p.name.split(".")[0] for d in gaz.block_dirs() if d.exists() for p in d.glob("*.tsv.gz")})
        info = {
            "data_dir": str(gaz.data_dir),
            "towns": prov.get("towns", {}),
            "postal": prov.get("postal", {}),
            "built": prov.get("built"),
            "block_prefectures": blocks,
        }
        if as_json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"Data dir:    {info['data_dir']}")
            print(f"Built:       {info['built']}")
            print(f"Towns:       {info['towns'].get('records')} ({info['towns'].get('dataset')})")
            print(f"Postal:      {info['postal'].get('records')} ({info['postal'].get('dataset')})")
            print(f"Attribution: {info['towns'].get('attribution')}")
            print(f"Blocks:      {', '.join(blocks) if blocks else 'none installed (jaden data fetch-blocks <pref>)'}")
        return 0

    target = user_data_dir()
    cache = target / "downloads"
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    if action == "update":
        prov = build_gazetteer.build(target, cache, log=log)
        print(f"Updated {prov['towns']['records']} towns and {prov['postal']['records']} postal codes in {target}")
    elif action == "fetch-blocks":
        if not prefectures or any(not 1 <= p <= 47 for p in prefectures):
            sys.stderr.write("Error: give one or more prefecture codes between 1 and 47 (e.g. 13 for Tokyo).\n")
            return EX_USAGE
        for pref in prefectures:
            meta = build_gazetteer.build_blocks(pref, target, cache, log=log)
            print(f"Installed {meta['records']} block points for prefecture {pref:02d} in {target / 'blocks'}")
    reset_gazetteer()
    return 0


# ==============================================================================
# CLI Entry Point & Argument Parsing
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Builds the top-level argument parser with subcommands."""
    parser = JadenArgumentParser(
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
        parser_class=JadenArgumentParser,
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
    norm_out = norm_p.add_mutually_exclusive_group()
    norm_out.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format.",
    )
    norm_out.add_argument(
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
    val_p.add_argument(
        "--strict",
        action="store_true",
        help="Also require the town to be found in the national gazetteer.",
    )

    # 4. geocode
    geo_p = subparsers.add_parser(
        "geocode",
        help="Resolve an address to geographic coordinates (WGS 84)",
        description="Resolves Japanese addresses to latitude/longitude using official open geospatial registries (GSI).",
    )
    geo_p.add_argument(
        "address",
        help="Japanese address string to geocode. Use '-' to read from stdin.",
    )
    geo_p.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON format.",
    )
    geo_p.add_argument(
        "--provider",
        default="gsi",
        choices=["gsi", "offline"],
        help="Geospatial provider: gsi (online API) or offline (bundled MLIT points). Default: gsi.",
    )
    geo_p.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Network timeout in seconds (default: 5.0).",
    )

    # 5. data
    data_p = subparsers.add_parser(
        "data",
        help="Show or refresh the gazetteer data (MLIT towns, Japan Post postal codes)",
        description="info: show what is installed. update: download the latest official datasets and rebuild. "
                    "fetch-blocks: install block-level points for prefectures (e.g. 13 for Tokyo).",
    )
    data_p.add_argument("action", choices=["info", "update", "fetch-blocks"])
    data_p.add_argument("prefectures", nargs="*", type=int, help="Prefecture codes for fetch-blocks (1-47).")
    data_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format (info).")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI main entry point."""
    if argv is None:
        raw_args = list(sys.argv[1:])
    else:
        raw_args = list(argv)

    # Pre-parse heuristic: if the first argument is not a known subcommand or flag,
    # default to 'normalize' for convenience and backward compatibility.
    known_cmds = {"normalize", "parse", "validate", "geocode", "data", "-h", "--help", "-v", "--version"}
    if raw_args and raw_args[0] not in known_cmds and (raw_args[0] == "-" or not raw_args[0].startswith("-")):
        raw_args.insert(0, "normalize")

    parser = build_parser()

    # If no arguments provided at all:
    if not raw_args:
        parser.print_help()
        return 0

    try:
        args = parser.parse_args(raw_args)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EX_USAGE

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "data":
        try:
            return handle_data(args.action, args.prefectures, as_json=args.json)
        except Exception as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return EX_SOFTWARE

    # Resolve address input (from argument or stdin when '-')
    target_address = args.address
    if target_address == "-":
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            target_address = stdin_content
        else:
            sys.stderr.write("Error: Address input from stdin is empty.\n")
            return EX_USAGE

    try:
        if args.command == "normalize":
            return handle_normalize(target_address, as_json=args.json, canonical_only=args.canonical_only)
        elif args.command == "parse":
            return handle_parse(target_address, as_json=args.json)
        elif args.command == "validate":
            return handle_validate(target_address, as_json=args.json, strict=args.strict)
        elif args.command == "geocode":
            return handle_geocode(target_address, as_json=args.json, provider=args.provider, timeout=args.timeout)
        else:
            parser.print_help()
            return EX_USAGE
    except Exception as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return EX_SOFTWARE


if __name__ == "__main__":
    sys.exit(main())
