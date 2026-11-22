"""Turning whatever a caller passes into text."""

import math
from typing import Any


def as_text(value: Any) -> str:
    """'' for None and NaN (an empty pandas cell); the text of anything else ('105' for 105).

    Public functions take strings, but data handed over from spreadsheets and data frames is often a
    number or a missing value: those become text instead of raising.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    if type(value).__name__ in ("NAType", "NaTType"):
        return ""
    return str(value)
