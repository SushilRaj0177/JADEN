"""JADEN: Finite-State Machine for Chome-Ban-Go and Banchi-Edaban parsing.

Supports:
- Statutory Gaiku-hoshiki (住居表示 街区方式): '6丁目10番1号', '10番1号', '6-10-1'
- Statutory Chiban (地番区域): '488番地', '488番地の1', '大字南長野字幅下692-2'
- Segmentation of Oaza (大字) and Koaza (字 / 小字)
- Conventional hyphenated notation and building tail isolation
"""

import re
from typing import Optional, Tuple, Dict, Any, Final
from ..core.constants import KANJI_DIGITS, KANJI_POWERS
from ..core.kanji_numerals import parse_kanji_number
from ..models.codes import AddressRegime

_KANJI_NUM_CHARS: Final[str] = "".join(list(KANJI_DIGITS.keys()) + list(KANJI_POWERS.keys()))
_NUM_TOKEN: Final[str] = rf"(?:\d+|[{_KANJI_NUM_CHARS}]+)"


def _parse_num(token: Optional[str]) -> Optional[int]:
    """Helper to parse either Arabic digits or Kanji numeral string."""
    if not token:
        return None
    token = token.strip()
    if token.isdigit():
        return int(token)
    return parse_kanji_number(token)


def extract_aza(town_raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Segments Oaza (大字) and Koaza (字 / 小字) from a cadastral town string."""
    # Pattern 1: Both 大字 and 字 present: e.g. '大字南長野字幅下' -> oaza='南長野', koaza='幅下'
    m_both = re.search(r"大字(?P<oaza>[^字\s\d]+?)(?:小字|字)(?P<koaza>[^\s\d]+)", town_raw)
    if m_both:
        return m_both.group("oaza"), m_both.group("koaza")

    # Pattern 2: Only 大字
    m_oaza = re.search(r"大字(?P<oaza>[^\s\d]+)", town_raw)
    oaza = m_oaza.group("oaza") if m_oaza else None

    # Pattern 3: Only 字 / 小字 (not preceded by 大)
    m_koaza = re.search(r"(?<!大)(?:小字|字)(?P<koaza>[^\s\d]+)", town_raw)
    koaza = m_koaza.group("koaza") if m_koaza else None

    return oaza, koaza


class BlockFSM:
    """Deterministic finite-state parser for block, lot, and house numbers."""

    @staticmethod
    def parse(text: str, has_chome_already: bool = False) -> Tuple[
        Dict[str, Any],  # numbers and regime dict
        str,             # Town name extracted before block
        str              # Tail string (building, floor, unit)
    ]:
        """Parses block and lot numbers from the town/block text segment.

        Args:
            text: Text segment following municipality/ward/kyoto-clause.
            has_chome_already: Whether chome was already extracted (e.g. from Hokkaido parser).

        Returns:
            Tuple of (result_dict, town_name, remaining_tail).
        """
        text = text.strip()
        result: Dict[str, Any] = {
            "chome": None,
            "ban": None,
            "go": None,
            "banchi": None,
            "edaban": None,
            "oaza": None,
            "koaza": None,
            "address_regime": AddressRegime.UNSPECIFIED.value,
        }

        if not text:
            return result, "", ""

        # =====================================================================
        # STATE 1: Explicit '丁目' marker present in string
        # =====================================================================
        chome_match = re.search(rf"^(?P<town>.*?)(?P<chome>{_NUM_TOKEN})丁目(?P<rest>.*)$", text)
        if chome_match:
            town = chome_match.group("town").strip()
            oaza, koaza = extract_aza(town)
            result["oaza"] = oaza
            result["koaza"] = koaza
            result["chome"] = _parse_num(chome_match.group("chome"))
            result["address_regime"] = AddressRegime.GAIKU_HOSHIKI.value
            rest = chome_match.group("rest").strip()

            # Parse numbers in rest following 丁目:
            # 1a. Named ban/banchi: '10番1号', '10番地の1', '10番地1'
            sub_named = re.search(
                rf"^(?P<ban>{_NUM_TOKEN})(?P<suffix>番地の|番地|番)(?:(?:の|-)?(?P<go>{_NUM_TOKEN})号?)?(?P<tail>.*)$",
                rest
            )
            if sub_named:
                ban_val = _parse_num(sub_named.group("ban"))
                go_val = _parse_num(sub_named.group("go"))
                suffix = sub_named.group("suffix")

                if "番地" in suffix:
                    result["banchi"] = ban_val
                    result["edaban"] = go_val
                    result["address_regime"] = AddressRegime.CHIBAN.value
                else:
                    result["ban"] = ban_val
                    result["go"] = go_val
                tail = sub_named.group("tail").strip()
                return result, town, tail

            # 1b. Hyphenated after 丁目: e.g. '10-1'
            sub_hyphen = re.search(rf"^(?P<ban>{_NUM_TOKEN})-(?P<go>{_NUM_TOKEN})(?P<tail>.*)$", rest)
            if sub_hyphen:
                result["ban"] = _parse_num(sub_hyphen.group("ban"))
                result["go"] = _parse_num(sub_hyphen.group("go"))
                tail = sub_hyphen.group("tail").strip()
                return result, town, tail

            # 1c. Single number with 号 or bare number: e.g. '10号' or '10'
            sub_single = re.search(rf"^(?P<num>{_NUM_TOKEN})(?:号)?(?P<tail>.*)$", rest)
            if sub_single:
                result["ban"] = _parse_num(sub_single.group("num"))
                tail = sub_single.group("tail").strip()
                return result, town, tail

            return result, town, rest

        # =====================================================================
        # STATE 2: Explicit '番地' or '番' marker present (no 丁目)
        # =====================================================================
        ban_match = re.search(
            rf"^(?P<town>.*?)(?P<ban>{_NUM_TOKEN})(?P<suffix>番地の|番地|番(?!町|丁|街|館|割|組|場|屋|通|筋))(?:(?:の|-)?(?P<go>{_NUM_TOKEN})号?)?(?P<tail>.*)$",
            text
        )
        if ban_match:
            town = ban_match.group("town").strip()
            oaza, koaza = extract_aza(town)
            result["oaza"] = oaza
            result["koaza"] = koaza

            ban_val = _parse_num(ban_match.group("ban"))
            go_val = _parse_num(ban_match.group("go"))
            suffix = ban_match.group("suffix")

            if "番地" in suffix or oaza is not None or koaza is not None:
                result["banchi"] = ban_val
                result["edaban"] = go_val
                result["address_regime"] = AddressRegime.CHIBAN.value
            else:
                result["ban"] = ban_val
                result["go"] = go_val
                if go_val is not None:
                    result["address_regime"] = AddressRegime.GAIKU_HOSHIKI.value
                else:
                    result["address_regime"] = AddressRegime.UNSPECIFIED.value

            tail = ban_match.group("tail").strip()
            return result, town, tail

        # =====================================================================
        # STATE 3: Hyphenated block notation (e.g. '6-10-1', '692-2', '10-1')
        # =====================================================================
        hyphen_match = re.search(
            r"^(?P<town>.*?)(?P<n1>\d+)-(?P<n2>\d+)(?:-(?P<n3>\d+))?(?P<tail>.*)$",
            text
        )
        if hyphen_match:
            town = hyphen_match.group("town").strip()
            oaza, koaza = extract_aza(town)
            result["oaza"] = oaza
            result["koaza"] = koaza

            n1 = int(hyphen_match.group("n1"))
            n2 = int(hyphen_match.group("n2"))
            n3 = int(hyphen_match.group("n3")) if hyphen_match.group("n3") else None

            if n3 is not None:
                # 3 numbers: Chome-Ban-Go (Statutory Gaiku-hoshiki)
                result["chome"] = n1
                result["ban"] = n2
                result["go"] = n3
                result["address_regime"] = AddressRegime.GAIKU_HOSHIKI.value
            else:
                # 2 numbers:
                if oaza is not None or koaza is not None:
                    # Cadastral area (地番区域): e.g. '大字南長野字幅下692-2'
                    result["banchi"] = n1
                    result["edaban"] = n2
                    result["address_regime"] = AddressRegime.CHIBAN.value
                elif has_chome_already:
                    result["ban"] = n1
                    result["go"] = n2
                    result["address_regime"] = AddressRegime.GAIKU_HOSHIKI.value
                else:
                    # Conventional hyphenated notation: mark unspecified regime
                    result["ban"] = n1
                    result["go"] = n2
                    result["address_regime"] = AddressRegime.UNSPECIFIED.value

            tail = hyphen_match.group("tail").strip()
            return result, town, tail

        # =====================================================================
        # STATE 4: Single number at tail of town (e.g. '488番地', '10番', or '1')
        # =====================================================================
        single_match = re.search(rf"^(?P<town>.*?)(?P<num>{_NUM_TOKEN})(?:番地|番|号)?(?P<tail>.*)$", text)
        if single_match and single_match.group("num"):
            town = single_match.group("town").strip()
            oaza, koaza = extract_aza(town)
            result["oaza"] = oaza
            result["koaza"] = koaza

            num = _parse_num(single_match.group("num"))
            if "番地" in text or oaza is not None or koaza is not None:
                result["banchi"] = num
                result["address_regime"] = AddressRegime.CHIBAN.value
            else:
                result["ban"] = num
                result["address_regime"] = AddressRegime.UNSPECIFIED.value

            tail = single_match.group("tail").strip()
            return result, town, tail

        # Default: Entire string is town name
        oaza, koaza = extract_aza(text)
        result["oaza"] = oaza
        result["koaza"] = koaza
        return result, text, ""
