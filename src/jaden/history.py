"""Municipal history: retired codes and the municipality an address belonged to before the mergers.

Japan's municipalities went from about 3,200 to about 1,700 between 1999 and 2010, and codes and wards keep
changing (浜松市, 2024). Records, registers and statistics made before a change still use the old names and
codes. This module answers two questions offline:

- ``current_codes(code)``: what does a code that no longer exists stand for today?
  ``'112267'`` (鳩ヶ谷市, merged into 川口市 on 2011-10-11) -> ``('112038',)``.
- ``former_municipality(address)``: which municipality was this address in on 2000-10-01, if that
  municipality has since been merged, split or renamed? ``'埼玉県さいたま市浦和区高砂3-15-1'`` -> 浦和市.

Sources (see ``jaden.data.build_former``): MLIT's 2000-10-01 municipal boundaries (国土数値情報 行政区域 N03),
overlaid on today's district points, and MIC's list of code changes since 2005-04-01.
"""

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .data.gazetteer import resolve_data_dir

__all__ = ["CodeChange", "FormerMunicipality", "code_change", "current_codes", "former_municipality"]


@dataclass(frozen=True, slots=True)
class CodeChange:
    """A municipality code that no longer exists, and the current codes its area now has."""
    code: str                      # the retired six-digit code
    name: str                      # its name then ('鳩ヶ谷市'; a ward without its city: '中区')
    prefecture_code: str
    successors: Tuple[str, ...]    # current six-digit codes
    date: str                      # ISO date of the change ('' when the source gives none)
    reason: str                    # as MIC states it ('合併後は川口市', '市制施行', ...)


@dataclass(frozen=True, slots=True)
class FormerMunicipality:
    """A municipality of 2000-10-01 that has since been merged, split or renamed."""
    code: str                      # its six-digit code in 2000
    name: str                      # '浦和市', '浜松市中区' (a ward with its city)
    county: str                    # '磐田郡' for towns and villages, else ''
    prefecture_code: str
    successors: Tuple[str, ...]    # current codes its area belongs to
    abolished: str                 # ISO date, or '2000-10-01/2005-03-31' when only the period is known


class _History:
    def __init__(self) -> None:
        self._changes: Optional[Dict[str, CodeChange]] = None
        self._formers: Optional[Dict[str, FormerMunicipality]] = None
        self._districts: Optional[Dict[Tuple[str, str, str], str]] = None

    @staticmethod
    def _path(name: str) -> Optional[Path]:
        for directory in (resolve_data_dir(), Path(__file__).parent / "data"):
            if (directory / name).exists():
                return directory / name
        return None

    def _load(self) -> None:
        if self._changes is not None:
            return
        changes: Dict[str, CodeChange] = {}
        formers: Dict[str, FormerMunicipality] = {}
        path = self._path("former_municipalities.json")
        if path is not None:
            data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            for e in data.get("entries", []):
                if e.get("former_code"):
                    formers[e["former_code"]] = FormerMunicipality(
                        e["former_code"], e["name"], e.get("county", ""), e["pref"], tuple(sorted(e["successors"])),
                        e.get("abolished", ""))
            for c in data.get("code_changes", []):
                changes[c["code"]] = CodeChange(c["code"], c["name"], c["pref"], tuple(c["successors"]),
                                                c.get("date", ""), c.get("reason", ""))
            # A 2000 code that changed before 2005-04-01 is not in MIC's list, only in the boundaries
            for code, f in formers.items():
                if code not in changes:
                    changes[code] = CodeChange(code, f.name, f.prefecture_code, f.successors, f.abolished, "")
        self._changes, self._formers = changes, formers

    def _load_districts(self) -> Dict[Tuple[str, str, str], str]:
        if self._districts is None:
            districts: Dict[Tuple[str, str, str], str] = {}
            path = self._path("former_districts.tsv.gz")
            if path is not None:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    next(f)
                    for line in f:
                        lg, key, chome, former, _name = line.rstrip("\n").split("\t")
                        districts[(lg, key, chome)] = former
            self._districts = districts
        return self._districts

    def change(self, code: str) -> Optional[CodeChange]:
        self._load()
        assert self._changes is not None
        return self._changes.get(_six(code))

    def former(self, code: str) -> Optional[FormerMunicipality]:
        self._load()
        assert self._formers is not None
        return self._formers.get(code)

    def district_former(self, lg_code: str, key: str, chome: str) -> Optional[str]:
        districts = self._load_districts()
        return districts.get((lg_code, key, chome)) or districts.get((lg_code, key, ""))


_HISTORY = _History()


def _six(code: str) -> str:
    code = str(code).strip()
    if len(code) == 5 and code.isdigit():
        r = sum(int(d) * w for d, w in zip(code, (6, 5, 4, 3, 2))) % 11
        return code + (str((11 - r) % 10) if r <= 1 else str(11 - r))
    return code


def code_change(code: str) -> Optional[CodeChange]:
    """The change that retired ``code`` (five or six digits), or None if the code is not a retired one."""
    return _HISTORY.change(code)


def current_codes(code: str) -> Tuple[str, ...]:
    """The current six-digit codes for ``code``: itself when it is current, its successors when it was
    retired, and () when it is neither."""
    from .data.loader import get_registry
    six = _six(code)
    if get_registry().get_municipality_by_code(six) is not None:
        return (six,)
    change = _HISTORY.change(six)
    return change.successors if change else ()


def former_municipality(address: Any) -> Optional[FormerMunicipality]:
    """The municipality ``address`` (a string or a NormalizedAddress) was in on 2000-10-01, when that
    municipality has since been merged, split or renamed; None when it is unchanged or the address does not
    reach a registered district."""
    from .core.townkey import town_key
    if isinstance(address, str):
        from . import normalize
        address = normalize(address)
    c = address.components
    if not c.lg_code or not c.town or c.town_verified is False:
        return None
    chome = str(c.chome) if c.chome is not None else ""
    code = _HISTORY.district_former(c.lg_code, town_key(c.town), chome)
    if code is None and c.koaza and c.town.endswith(c.koaza):
        # The district table is at 大字 level: a 小字 lies inside its 大字 ('藤沢町大籠字右名沢' -> '藤沢町大籠')
        # Only when the 小字 is marked as such: '大字東貝塚' has no 小字, whatever the parse says
        parent = c.town[:-len(c.koaza)]
        marked = parent.endswith("字") and not parent.endswith("大字")
        parent = parent[:-2] if parent.endswith("小字") else parent[:-1]
        if marked and parent:
            code = _HISTORY.district_former(c.lg_code, town_key(parent), chome)
    return _HISTORY.former(code) if code else None
