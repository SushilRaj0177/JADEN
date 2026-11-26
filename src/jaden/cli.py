"""JADEN: High-performance Command-Line Interface.

Provides clean, professional commands for Japanese address data engineering:
  jaden normalize "<address>" [--json] [-c]
  jaden parse "<address>" [--json]
  jaden validate "<address>" [--json]
  jaden geocode "<address>" [--json] [--provider gsi|offline]
  jaden data info | update | fetch-blocks <pref>...
  jaden batch <file> [-o out] [--column 住所] [--jobs N]
  jaden compare "<address A>" "<address B>"
  jaden dedupe <file> [-o out] [--level unit|house|block|town]
  jaden postal <code>            postal code -> addresses
  jaden suggest "<partial>"      autocomplete
  jaden reverse <lat> <lon>      coordinate -> nearest town / 丁目 / block
  jaden extract <file>           find the addresses inside a text
  jaden serve [--port 8000]      JSON API for all of the above, with a demo page
"""

import re
import sys
import argparse
import json
from typing import Optional, Sequence, List, Final, NoReturn, Any, Tuple

# Standard sysexits codes for CLI errors
EX_USAGE: Final[int] = 64      # Command-line usage error, unknown flag, missing arg, empty stdin
EX_SOFTWARE: Final[int] = 70   # Internal unhandled software crash

# Ensure UTF-8 I/O encoding on Windows platforms
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")   # one broken character must not stop a run
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
    for s in res.suggestions:
        lines.append(f"Suggestion: {s}")
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
    elif c.chome_unlisted:
        text += f"; {c.chome}丁目 is not in the registry"
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
    if v.precision != "none":
        lines.append(f"Precision:   {v.precision}")
    for s in v.suggestions:
        lines.append(f"Suggestion:  {s}")
    if v.message:
        lines.append(f"Message:     {v.message}")
    for w in v.warnings:
        if w not in v.message:
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

def handle_normalize(address: str, as_json: bool, canonical_only: bool, fix: bool = False,
                     style: str = "canonical") -> int:
    """Executes the normalize command."""
    res = normalize(address, autocorrect=fix)

    if as_json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    elif canonical_only:
        print(res.format(style) if res.confidence_score > 0 else res.canonical)
    else:
        print(format_normalize_text(res))

    return 0 if res.confidence_score > 0.0 else 1


def handle_label(address: str, size: Tuple[int, int], as_json: bool = False, fix: bool = False, count: str = "chars",
                 fullwidth: bool = False, style: str = "canonical") -> int:
    """Prints the address split into label lines; exit 1 when it does not fit."""
    res = normalize(address, autocorrect=fix)
    label = res.label(size[0], size[1], count=count, style="hyphen" if style == "canonical" else style,
                      fullwidth=fullwidth)
    if as_json:
        print(json.dumps(label.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("\n".join(label.lines))
        if not label.fits:
            sys.stderr.write(f"Does not fit: '{label.overflow}' left over\n")
    return 0 if label.fits and res.confidence_score > 0 else 1


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


def handle_validate(address: str, as_json: bool, strict: bool = False, fix: bool = False) -> int:
    """Executes the validate command with status-specific exit codes."""
    val = validate(address, strict=strict, autocorrect=fix)

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


def _municipality_list_info() -> dict:
    from pathlib import Path
    from .data.build_municipalities import SOURCE_METADATA
    from .data.loader import get_registry
    registry = get_registry()
    path = registry.municipality_list_path()
    meta_path = path.parent / "municipalities_provenance.json"
    if path.parent != Path(__file__).parent / "data" and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {"records": meta.get("records"), "dataset": meta.get("dataset_name"), "source": str(path)}
    return {"records": len(registry.list_municipalities()), "dataset": SOURCE_METADATA["dataset_name"], "source": "bundled"}


def handle_data(action: str, prefectures: Sequence[int], as_json: bool) -> int:
    """Shows, refreshes, or extends the gazetteer data from the official open-data sources."""
    from .data.gazetteer import get_gazetteer, reset_gazetteer, user_data_dir
    from .data.loader import reset_registry
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
            "block_prefectures_to_refetch": gaz.stale_block_prefectures(),
            "municipality_list": _municipality_list_info(),
        }
        if as_json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"Data dir:    {info['data_dir']}")
            print(f"Built:       {info['built']}")
            print(f"Towns:       {info['towns'].get('records')} ({info['towns'].get('dataset')})")
            print(f"Postal:      {info['postal'].get('records')} ({info['postal'].get('dataset')})")
            print(f"Attribution: {info['towns'].get('attribution')}")
            ml = info["municipality_list"]
            print(f"Municipalities: {ml['records']} ({ml['dataset']}; {ml['source']})")
            print(f"Blocks:      {', '.join(blocks) if blocks else 'none installed (jaden data fetch-blocks <pref>)'}")
            stale = info["block_prefectures_to_refetch"]
            if stale:
                print(f"             built by an older version, re-fetch for full coverage: "
                      f"jaden data fetch-blocks {' '.join(str(int(x)) for x in stale)}")
        return 0

    target = user_data_dir()
    cache = target / "downloads"
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    if action == "update":
        from .data import build_municipalities
        try:
            muni = build_municipalities.refresh(target, cache, log=log)
            print(f"Municipality list: {muni['label']}, {muni['records']} records"
                  + (f" ({len(muni['added'])} added, {len(muni['removed'])} removed)" if muni["changed"] else
                     " (same as the bundled list)"))
            reset_registry()
        except Exception as exc:   # the towns and postal codes are still worth updating
            sys.stderr.write(f"Warning: municipality list not refreshed: {exc}\n")
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
    norm_p.add_argument(
        "--style",
        choices=["canonical", "hyphen", "en"],
        default="canonical",
        help="With -c: 4丁目2番8号 (canonical), 4-2-8 (hyphen) or the English line (en).",
    )
    norm_p.add_argument(
        "--fix",
        action="store_true",
        help="Correct a misspelt town when exactly one registered town is one character away.",
    )
    norm_p.add_argument(
        "--label", metavar="WIDTHxLINES", type=_label_size,
        help="Print the address split into label lines, e.g. 20x3 (at most 3 lines of 20 characters). "
             "Exit code 1 when it does not fit.",
    )
    norm_p.add_argument("--label-bytes", action="store_true",
                        help="With --label: count Shift_JIS bytes (full-width 2, half-width 1) instead of characters.")
    norm_p.add_argument("--fullwidth", action="store_true",
                        help="With --label: write digits, letters and hyphens in full width.")

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
    val_p.add_argument(
        "--fix",
        action="store_true",
        help="Correct a misspelt town when exactly one registered town is one character away.",
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

    # 5. batch
    batch_p = subparsers.add_parser(
        "batch",
        help="Process a CSV / TSV / JSONL / text file of addresses",
        description="Resolves the address column of every row and writes the rows back with jaden_* result "
                    "columns appended. Input encoding (UTF-8 or Shift_JIS) is detected.",
    )
    _file_arguments(batch_p)
    batch_p.add_argument("--strict", action="store_true", help="Require town-level verification for ACCEPTED.")
    batch_p.add_argument("--fix", action="store_true",
                         help="Correct misspelt towns (unique one-character corrections only; the original is reported).")
    batch_p.add_argument("--jobs", type=_positive_int, default=1, help="Worker processes (default: 1).")
    batch_p.add_argument("--resolve", action="store_true",
                         help="Add the calibrated resolver's columns (municipality, probability, candidates) "
                              "for addresses that leave out their municipality.")
    batch_p.add_argument("--name-column", metavar="COLUMN",
                         help="With --resolve: column holding a company or facility name to use as evidence.")

    _add_toolkit_parsers(subparsers)
    _add_lookup_parsers(subparsers)
    _add_audit_parser(subparsers)

    # data
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


# ==============================================================================
# Toolkit commands (matching, lookup, extraction, server)
# ==============================================================================

def _file_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", help="Input file (.csv, .tsv, .jsonl, .xlsx, or text with one address per line); "
                                 "'-' for stdin.")
    p.add_argument("-o", "--output", help="Output file (format from its extension, .xlsx included); default: stdout.")
    p.add_argument("--column", help="Address column name or 1-based number (default: a column named "
                                    "address/住所/所在地, else the first). For JSONL, the key (default: address).")
    p.add_argument("--format", choices=["csv", "tsv", "jsonl", "txt", "xlsx"],
                   help="Input format (default: from extension; .xlsx reads the first worksheet).")
    p.add_argument("--encoding", help="Input encoding (default: detect UTF-8 / UTF-16 / Shift_JIS / EUC-JP).")
    p.add_argument("--output-encoding", default="utf-8",
                   help="Output encoding; utf-8-sig opens cleanly in Excel, cp932 is Shift_JIS (default: utf-8).")
    p.add_argument("--no-header", action="store_true",
                   help="The CSV / TSV has no header row (default: detected; a first row that is an address is data).")


def _add_toolkit_parsers(subparsers: Any) -> None:
    cmp_p = subparsers.add_parser(
        "compare",
        help="Tell whether two addresses are the same place",
        description="Compares two addresses level by level (municipality, town, 丁目, block, house, room). "
                    "Exit code: 0 same, 1 different, 2 same building / possibly the same, 3 undetermined.",
    )
    cmp_p.add_argument("a", help="First address.")
    cmp_p.add_argument("b", help="Second address.")
    cmp_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")

    dd_p = subparsers.add_parser(
        "dedupe",
        help="Group the rows of a file that have the same address (名寄せ)",
        description="Appends jaden_match_key, jaden_group and jaden_group_size to every row. Rows with the "
                    "same group number have the same address at the chosen level.",
    )
    _file_arguments(dd_p)
    dd_p.add_argument("--level", choices=["unit", "house", "block", "chome", "town"], default="unit",
                      help="How precisely addresses must agree (default: unit = same house and same room).")
    dd_p.add_argument("--pairs", metavar="FILE",
                      help="Also write likely duplicate pairs (same block) to this CSV, with a score and the reasons; "
                           "catches near-matches such as a misspelt building name or a missing room. row_a and "
                           "row_b count data rows from 1 (a header row is not counted).")
    dd_p.add_argument("--min-score", type=_score, default=0.5,
                      help="Lowest pair score written with --pairs, from 0 to 1 (default: 0.5).")


def _add_audit_parser(subparsers: Any) -> None:
    au_p = subparsers.add_parser(
        "audit",
        help="Check that each row's address agrees with its municipality code",
        description="Reads each row's address on its own and compares it with the row's municipality code. "
                    "Appends jaden_audit (consistent, consistent_former_name, code_retired, conflict, "
                    "district_not_in_claimed, undetermined, unreadable, code_invalid), the code's status, the "
                    "municipality the address names, a suggested code and a short explanation. "
                    "A conflict is a disagreement to look at, not proof that the code is wrong.",
    )
    _file_arguments(au_p)
    au_p.add_argument("--code-column", required=True,
                      help="Column (name or 1-based number; for JSONL, the key) holding the municipality code "
                           "(5 or 6 digits).")


def _label_size(value: str) -> Tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[xX×*]\s*(\d+)\s*", value)
    if not m or int(m.group(1)) < 4 or int(m.group(2)) < 1:
        raise argparse.ArgumentTypeError("use WIDTHxLINES, e.g. 20x3 (width at least 4)")
    return int(m.group(1)), int(m.group(2))


def _score(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1") from None
    if not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1")
    return number


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _add_lookup_parsers(subparsers: Any) -> None:
    po_p = subparsers.add_parser(
        "postal", help="Look up the addresses a postal code covers",
        description="Postal code (105-0011, 1050011, 〒105-0011) -> prefecture, municipality, town, readings.")
    po_p.add_argument("code", help="7-digit postal code.")
    po_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")

    su_p = subparsers.add_parser(
        "suggest", help="Complete a partly typed address or postal code",
        description="Autocomplete: municipalities, towns (by spelling or reading), 丁目, or postal codes.")
    su_p.add_argument("text", help="Partial address ('東京都港区芝', '港区しば') or postal code ('105-00').")
    su_p.add_argument("--limit", type=_positive_int, default=10, help="Maximum number of suggestions (default: 10).")
    su_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")

    ex_p = subparsers.add_parser(
        "extract", help="Find the addresses inside a text file",
        description="Prints every address found with its line, character span, status and canonical form. "
                    "Exit code 1 when the text contains no address.")
    ex_p.add_argument("input", help="Text file; '-' for stdin.")
    ex_p.add_argument("--encoding", help="Input encoding (default: detect UTF-8 / Shift_JIS).")
    ex_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")

    sv_p = subparsers.add_parser(
        "serve", help="Run the JSON API server (and demo page)",
        description="Serves every JADEN function as a JSON API under /v1 and a demo page at /. "
                    "Standard library only; all lookups use the local data.")
    sv_p.add_argument("--host", default="127.0.0.1", help="Address to bind (default: 127.0.0.1; use 0.0.0.0 to expose).")
    sv_p.add_argument("--port", type=int, default=8000, help="Port (default: 8000).")
    sv_p.add_argument("--cors", metavar="ORIGIN", help="Send Access-Control-Allow-Origin for this origin ('*' for any).")
    sv_p.add_argument("--max-batch", type=int, default=1000, help="Most addresses accepted by /v1/batch (default: 1000).")
    sv_p.add_argument("--quiet", action="store_true", help="Do not log requests.")

    st_p = subparsers.add_parser(
        "stream", help="Read addresses line by line from stdin, write one JSON record per line",
        description="NDJSON streaming for pipelines: each input line is an address, a JSON string, or a JSON "
                    "object holding the address; each output line is {\"input\": ..., \"jaden\": {...}}, "
                    "written as soon as the line is read.")
    st_p.add_argument("--column", default="address", help="Key of the address in JSON objects (default: address).")
    st_p.add_argument("--strict", action="store_true", help="Require town-level verification for ACCEPTED.")
    st_p.add_argument("--fix", action="store_true", help="Correct misspelt towns.")
    st_p.add_argument("--resolve", action="store_true", help="Add the calibrated resolver's fields.")
    st_p.add_argument("--name-column", metavar="KEY", help="With --resolve: key holding a company or facility name.")

    subparsers.add_parser(
        "mcp", help="Run as an MCP server for AI assistants (stdin/stdout)",
        description="Model Context Protocol server over stdin/stdout: normalize, validate, resolve, extract, "
                    "postal lookup, compare and autocomplete as tools. Register it in the assistant's MCP "
                    "settings as the command 'jaden mcp'.")

    rs_p = subparsers.add_parser(
        "resolve", help="Rank the candidate municipalities of an address with calibrated probabilities",
        description="For addresses that do not name their municipality: every candidate with a probability, "
                    "the answer when it clears the 1%-risk threshold, and a 95% candidate set. "
                    "Exit code 0 when an answer is given, 3 when not.")
    rs_p.add_argument("address", help="Address, e.g. '錦町1番2号'; '-' reads one address per line from stdin.")
    rs_p.add_argument("--name", default="", help="Organisation or facility at the address (optional evidence).")
    rs_p.add_argument("--limit", type=_positive_int, default=10, help="Candidates to show (default: 10).")
    rs_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")

    rv_p = subparsers.add_parser(
        "reverse", help="Find the registered town nearest to a coordinate (offline)",
        description="Latitude and longitude -> nearest town / 丁目 point (block with block data installed).")
    rv_p.add_argument("latitude", type=float)
    rv_p.add_argument("longitude", type=float)
    rv_p.add_argument("--limit", type=_positive_int, default=1, help="Number of nearest places to return (default: 1).")
    rv_p.add_argument("--json", action="store_true", help="Output machine-readable JSON format.")


def _handle_resolve(args: argparse.Namespace) -> int:
    if args.address == "-":
        lines = [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]
        if not lines:
            sys.stderr.write("Error: Address input from stdin is empty.\n")
            return EX_USAGE
        codes = [_resolve_one(argparse.Namespace(**{**vars(args), "address": ln})) for ln in lines]
        return max(codes)
    return _resolve_one(args)


def _resolve_one(args: argparse.Namespace) -> int:
    import dataclasses
    import json
    from .resolve import resolve
    r = resolve(args.address, args.name)
    if args.json:
        data = dataclasses.asdict(r)
        data["candidates"] = data["candidates"][:args.limit]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"Input:      {r.input}" + (f"  (name: {r.side})" if r.side else ""))
        print(f"Rules:      {r.rules_status}")
        if r.answered:
            print(f"Answer:     {r.name} ({r.lg_code}), p = {r.probability:.3f}")
        else:
            print(f"Answer:     none: the best candidate's p = {r.probability:.3f} is below {r.threshold:.3f}")
        print(f"95% set:    {len(r.candidate_set)} candidate(s)" + (" or none of them" if r.set_includes_none else ""))
        for c in r.candidates[:args.limit]:
            print(f"  {c.probability:6.3f}  {c.name} ({c.lg_code})")
        if len(r.candidates) > args.limit:
            print(f"  ... {len(r.candidates) - args.limit} more")
        print(f"  {r.none_probability:6.3f}  none of these")
    return 0 if r.answered else 3


def _handle_stream(args: argparse.Namespace) -> int:
    from .frame import stream
    if args.name_column and not args.resolve:
        sys.stderr.write("Error: --name-column is evidence for --resolve; add --resolve.\n")
        return EX_USAGE
    reconfigure = getattr(sys.stdin, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")
    stream(column=args.column, strict=args.strict, fix=args.fix, resolve=args.resolve, name_column=args.name_column)
    return 0


def _handle_mcp(args: argparse.Namespace) -> int:
    from .mcp import serve_stdio
    return serve_stdio()


def _handle_serve(args: argparse.Namespace) -> int:
    from .server import serve
    return serve(host=args.host, port=args.port, cors=args.cors, quiet=args.quiet, max_batch=args.max_batch)


def _handle_extract(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .batch import read_text
    from .extract import extract_addresses
    text = read_text(Path(args.input), args.encoding)
    found = extract_addresses(text)
    if args.json:
        print(json.dumps([x.to_dict() for x in found], ensure_ascii=False, indent=2))
    else:
        for x in found:
            line = text.count("\n", 0, x.start) + 1
            print(f"{line}:{x.start}-{x.end}\t{x.status}\t{x.canonical}\t{x.text!r}")
    return 0 if found else 1


def _handle_postal(args: argparse.Namespace) -> int:
    from .lookup import lookup_postal
    found = lookup_postal(args.code)
    if args.json:
        print(json.dumps([p.to_dict() for p in found], ensure_ascii=False, indent=2))
    elif not found:
        print(f"No address for postal code '{args.code}'.")
    else:
        for p in found:
            print(f"〒{p.postal_code}  {p.address}" + (f"  [{p.building}]" if p.building else ""))
            print(f"            {p.kana}")
            print(f"            {p.romaji}")
    return 0 if found else 1


def _handle_suggest(args: argparse.Namespace) -> int:
    from .lookup import suggest
    found = suggest(args.text, limit=args.limit)
    if args.json:
        print(json.dumps([s.to_dict() for s in found], ensure_ascii=False, indent=2))
    else:
        for s in found:
            print(s.text + (f"  〒{s.postal_code}" if s.postal_code else ""))
    return 0 if found else 1


def _handle_reverse(args: argparse.Namespace) -> int:
    from .lookup import reverse_geocode
    found = reverse_geocode(args.latitude, args.longitude, limit=args.limit)
    if args.json:
        print(json.dumps([r.to_dict() for r in found], ensure_ascii=False, indent=2))
    elif not found:
        print("No registered town within 30 km of that point.")
    else:
        for r in found:
            print(f"{r.address}  ({r.level} point, {r.distance_m:.0f} m away)"
                  + (f"  〒{r.postal_code}" if r.postal_code else ""))
    return 0 if found else 1


def _handle_compare(args: argparse.Namespace) -> int:
    from .matching import compare
    result = compare(args.a, args.b)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"A:        {result.canonical_a or result.a}")
        print(f"B:        {result.canonical_b or result.b}")
        print(f"Verdict:  {result.verdict}")
        print(f"Agree to: {result.level}")
        if result.conflict:
            print(f"Conflict: {result.conflict}")
        if result.missing:
            print(f"Missing:  {', '.join(result.missing)} (on one side)")
        for note in result.notes:
            print(f"Note:     {note}")
    return {"same": 0, "different": 1, "undetermined": 3}.get(result.verdict, 2)


def _handle_audit(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .batch import run_audit
    run_audit(Path(args.input), Path(args.output) if args.output else None, code_column=args.code_column,
              fmt=args.format, column=args.column, encoding=args.encoding, out_encoding=args.output_encoding,
              header_row=False if args.no_header else None)
    return 0


def _handle_dedupe(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .batch import run_dedupe
    run_dedupe(Path(args.input), Path(args.output) if args.output else None, fmt=args.format, column=args.column,
               encoding=args.encoding, out_encoding=args.output_encoding, level=args.level,
               header_row=False if args.no_header else None,
               pairs=Path(args.pairs) if args.pairs else None, min_score=args.min_score)
    return 0


_TOOLKIT_HANDLERS = {
    "compare": _handle_compare,
    "dedupe": _handle_dedupe,
    "audit": _handle_audit,
    "postal": _handle_postal,
    "suggest": _handle_suggest,
    "reverse": _handle_reverse,
    "resolve": _handle_resolve,
    "extract": _handle_extract,
    "serve": _handle_serve,
    "mcp": _handle_mcp,
    "stream": _handle_stream,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI main entry point."""
    if argv is None:
        raw_args = list(sys.argv[1:])
    else:
        raw_args = list(argv)

    # Pre-parse heuristic: if the first argument is not a known subcommand or flag,
    # default to 'normalize' for convenience and backward compatibility.
    known_cmds = {"normalize", "parse", "validate", "geocode", "data", "batch", "-h", "--help", "-v", "--version",
                  *_TOOLKIT_HANDLERS}
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

    if args.command == "batch":
        from pathlib import Path
        from .batch import run_batch
        if args.name_column and not args.resolve:
            sys.stderr.write("Error: --name-column is evidence for --resolve; add --resolve.\n")
            return EX_USAGE
        try:
            run_batch(Path(args.input), Path(args.output) if args.output else None, fmt=args.format,
                      column=args.column, encoding=args.encoding, out_encoding=args.output_encoding,
                      strict=args.strict, jobs=max(1, args.jobs), autocorrect=args.fix,
                      header_row=False if args.no_header else None, resolve=args.resolve,
                      name_column=args.name_column)
            return 0
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return EX_USAGE

    if args.command in _TOOLKIT_HANDLERS:
        try:
            return _TOOLKIT_HANDLERS[args.command](args)
        except (ValueError, OSError, UnicodeDecodeError) as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return EX_USAGE

    if args.command == "data":
        try:
            return handle_data(args.action, args.prefectures, as_json=args.json)
        except Exception as exc:
            sys.stderr.write(f"Error: {exc}\n")
            return EX_SOFTWARE

    # Resolve address input (from argument or stdin when '-'): one address per line
    if args.address == "-":
        lines = [ln.strip() for ln in sys.stdin.read().splitlines() if ln.strip()]
        if not lines:
            sys.stderr.write("Error: Address input from stdin is empty.\n")
            return EX_USAGE
    else:
        lines = [args.address]
    return max(_run_address_command(parser, args, line) for line in lines)


def _run_address_command(parser: argparse.ArgumentParser, args: argparse.Namespace, target_address: str) -> int:
    try:
        if args.command == "normalize":
            if args.label:
                return handle_label(target_address, args.label, as_json=args.json, fix=args.fix,
                                    count="bytes" if args.label_bytes else "chars", fullwidth=args.fullwidth,
                                    style=args.style)
            return handle_normalize(target_address, as_json=args.json, canonical_only=args.canonical_only,
                                    fix=args.fix, style=args.style)
        elif args.command == "parse":
            return handle_parse(target_address, as_json=args.json)
        elif args.command == "validate":
            return handle_validate(target_address, as_json=args.json, strict=args.strict, fix=args.fix)
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
