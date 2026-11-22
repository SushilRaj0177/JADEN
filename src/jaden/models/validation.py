"""JADEN: Strongly-typed validation data models.

Provides ValidationStatus and ValidationResult for statutory and structural
integrity assessment of Japanese addresses.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import json


# Every reason code validate() returns, with its status: stable identifiers for programs and forms
REASONS: Dict[str, str] = {
    "VERIFIED_CHOME": "ACCEPTED",            # municipality, town and 丁目 found in the registries
    "VERIFIED_TOWN": "ACCEPTED",             # municipality and town found
    "VERIFIED_MUNICIPALITY": "ACCEPTED",     # only the municipality could be verified (see warnings)
    "AMBIGUOUS_MUNICIPALITY": "AMBIGUOUS",   # several municipalities fit; see ambiguous_candidates
    "EMPTY": "MALFORMED",
    "TOO_LONG": "MALFORMED",
    "NOT_AN_ADDRESS": "MALFORMED",           # no prefecture, municipality or registered town found
    "PREFECTURE_MISMATCH": "MALFORMED",      # the municipality is not in the prefecture written
    "NONEXISTENT_CHOME": "MALFORMED",
    "TOWN_IN_OTHER_MUNICIPALITY": "MALFORMED",
    "POSTAL_CODE_MISMATCH": "MALFORMED",
    "IMPOSSIBLE_NUMBER": "MALFORMED",        # a 丁目, block or lot numbered 0
    "UNPARSED_TEXT": "UNSUPPORTED",
    "NAME_NOT_ADDRESS": "UNSUPPORTED",       # a facility name that mentions a place, without block numbers
    "STRICT_TOWN_UNVERIFIED": "UNSUPPORTED",
    "STRICT_CHOME_UNLISTED": "UNSUPPORTED",
    "UNRESOLVED": "UNSUPPORTED",
}


class ValidationStatus(str, Enum):
    """Validation outcome classification for Japanese addresses."""
    ACCEPTED = "ACCEPTED"
    AMBIGUOUS = "AMBIGUOUS"
    MALFORMED = "MALFORMED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Represents statutory and structural validation outcome for an address."""
    raw_input: str
    status: str                         # 'ACCEPTED', 'AMBIGUOUS', 'MALFORMED', 'UNSUPPORTED'
    valid: bool                         # True if and only if status == 'ACCEPTED'
    confidence_score: float
    address_regime: str
    lg_code: Optional[str] = None
    is_ambiguous: bool = False
    ambiguous_candidates: Tuple[str, ...] = field(default_factory=tuple)
    message: str = ""
    verification_level: str = "none"   # 'none', 'municipality', 'town', 'chome'
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    precision: str = "none"            # 'unit', 'house', 'block', 'chome', 'town', 'municipality', 'prefecture', 'none'
    suggestions: Tuple[str, ...] = field(default_factory=tuple)  # corrected addresses for a misspelt town
    reason: str = ""                    # machine-readable reason code (see REASONS)
    message_ja: str = ""                # the message in Japanese

    def to_dict(self) -> Dict[str, Any]:
        """Serializes validation result to clean dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes validation result to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
