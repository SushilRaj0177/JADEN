"""Turning whatever a caller passes into text."""

import math
import re
from typing import Any

_SURROGATE = re.compile("[\ud800-\udfff]")


def encodable(text: str) -> str:
    """The text with lone surrogates (which no encoding can write) replaced by U+FFFD."""
    return _SURROGATE.sub("\ufffd", text) if text else text


def as_text(value: Any) -> str:
    """'' for None and NaN (an empty pandas cell); the text of anything else ('105' for 105).

    Public functions take strings, but data handed over from spreadsheets and data frames is often a
    number or a missing value: those become text instead of raising.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return encodable(value)
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if type(value).__name__ in ("NAType", "NaTType"):
        return ""
    return str(value)


def postal_text(value: Any) -> str:
    """A postal code as text. One given as a number (a spreadsheet drops the leading zero of 0600063) comes
    back as its seven digits."""
    if isinstance(value, bool):
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and 0 <= value < 10_000_000:
        return f"{value:07d}"
    return as_text(value)
