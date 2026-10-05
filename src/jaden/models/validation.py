"""JADEN: Strongly-typed validation data models.

Provides ValidationStatus and ValidationResult for statutory and structural
integrity assessment of Japanese addresses.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import json


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

    def to_dict(self) -> Dict[str, Any]:
        """Serializes validation result to clean dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes validation result to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
