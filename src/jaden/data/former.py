"""JADEN: Lookup of former municipality names (see build_former.py)."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .gazetteer import resolve_data_dir

_MAX_NAME_CHARS = 16


@dataclass(frozen=True, slots=True)
class FormerMunicipality:
    prefecture_code: str
    name: str                     # as written then: '浦和市', '浜松市中区', '浅羽町'
    county: str                   # '磐田郡' for towns and villages, else ''
    successors: Tuple[str, ...]   # current LG codes the area now belongs to
    as_of: str


class FormerMunicipalities:
    def __init__(self) -> None:
        self._by_name: Optional[Dict[str, List[FormerMunicipality]]] = None

    def _load(self) -> Dict[str, List[FormerMunicipality]]:
        if self._by_name is None:
            by_name: Dict[str, List[FormerMunicipality]] = {}
            for directory in (resolve_data_dir(), Path(__file__).parent):
                path = directory / "former_municipalities.json"
                if path.exists():
                    for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
                        rec = FormerMunicipality(e["pref"], e["name"], e.get("county", ""),
                                                 tuple(e["successors"]), e.get("as_of", ""))
                        by_name.setdefault(rec.name, []).append(rec)
                        if rec.county:
                            by_name.setdefault(rec.county + rec.name, []).append(rec)
                    break
            self._by_name = by_name
        return self._by_name

    def match(self, text: str, prefecture_code: Optional[str] = None) -> Optional[Tuple[List[FormerMunicipality], int]]:
        """Former municipalities whose name starts ``text`` (longest name wins)."""
        by_name = self._load()
        for end in range(min(len(text), _MAX_NAME_CHARS), 1, -1):
            found = by_name.get(text[:end])
            if found:
                if prefecture_code:
                    found = [f for f in found if f.prefecture_code == prefecture_code]
                if found:
                    return found, end
        return None


_FORMER: Optional[FormerMunicipalities] = None


def get_former_municipalities() -> FormerMunicipalities:
    global _FORMER
    if _FORMER is None:
        _FORMER = FormerMunicipalities()
    return _FORMER
