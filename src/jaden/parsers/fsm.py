"""JADEN: Finite-State Machine for Chome-Ban-Go and Banchi-Edaban parsing.

Supports:
- Statutory Gaiku-hoshiki: '6丁目10番1号', '10番1号'
- Statutory Chiban: '488番地', '488番地の1', '488番地1'
- Conventional hyphenated notation: '6-10-1', '10-1', '6丁目10-1'
- Mixed and concatenated formats: isolating building/floor tails
"""

import re
from typing import Optional, Tuple, Dict, Any, Final


class BlockFSM:
    """Deterministic finite-state parser for block, lot, and house numbers."""

    @staticmethod
    def parse(text: str, has_chome_already: bool = False) -> Tuple[
        Dict[str, Optional[int]],  # {'chome': ..., 'ban': ..., 'go': ..., 'banchi': ..., 'edaban': ...}
        str,                       # Town name extracted before block
        str                        # Tail string (building, floor, unit)
    ]:
        """Parses block and lot numbers from the town/block text segment.

        Args:
            text: Text segment following municipality/ward/kyoto-clause.
            has_chome_already: Whether chome was already extracted (e.g. from Hokkaido parser).

        Returns:
            Tuple of (numbers_dict, town_name, remaining_tail).
        """
        text = text.strip()
        result: Dict[str, Optional[int]] = {
            "chome": None,
            "ban": None,
            "go": None,
            "banchi": None,
            "edaban": None,
        }

        if not text:
            return result, "", ""

        # =====================================================================
        # STATE 1: Explicit '丁目' marker present in string
        # =====================================================================
        chome_match = re.search(r"^(?P<town>.*?)(?P<chome>\d+)丁目(?P<rest>.*)$", text)
        if chome_match:
            town = chome_match.group("town").strip()
            result["chome"] = int(chome_match.group("chome"))
            rest = chome_match.group("rest").strip()

            # Parse numbers in rest following 丁目:
            # e.g., '10番1号', '10番地1', '10-1', '10番', '10'
            sub_named = re.search(
                r"^(?P<ban>\d+)(?P<suffix>番地の|番地|番)(?:(?:の|-)?(?P<go>\d+)号?)?(?P<tail>.*)$",
                rest
            )
            if sub_named:
                ban_val = int(sub_named.group("ban"))
                go_val = int(sub_named.group("go")) if sub_named.group("go") else None
                suffix = sub_named.group("suffix")

                if "番地" in suffix:
                    result["banchi"] = ban_val
                    result["edaban"] = go_val
                else:
                    result["ban"] = ban_val
                    result["go"] = go_val
                tail = sub_named.group("tail").strip()
                return result, town, tail

            # Hyphenated after 丁目: e.g. '10-1'
            sub_hyphen = re.search(r"^(?P<ban>\d+)-(?P<go>\d+)(?P<tail>.*)$", rest)
            if sub_hyphen:
                result["ban"] = int(sub_hyphen.group("ban"))
                result["go"] = int(sub_hyphen.group("go"))
                tail = sub_hyphen.group("tail").strip()
                return result, town, tail

            # Single number with 号 or bare number: e.g. '10号' or '10'
            sub_single = re.search(r"^(?P<num>\d+)(?:号)?(?P<tail>.*)$", rest)
            if sub_single:
                result["ban"] = int(sub_single.group("num"))
                tail = sub_single.group("tail").strip()
                return result, town, tail

            return result, town, rest

        # =====================================================================
        # STATE 2: Explicit '番地' or '番' marker present (no 丁目)
        # =====================================================================
        ban_match = re.search(
            r"^(?P<town>.*?)(?P<ban>\d+)(?P<suffix>番地の|番地|番)(?:(?:の|-)?(?P<go>\d+)号?)?(?P<tail>.*)$",
            text
        )
        if ban_match:
            town = ban_match.group("town").strip()
            ban_val = int(ban_match.group("ban"))
            go_val = int(ban_match.group("go")) if ban_match.group("go") else None
            suffix = ban_match.group("suffix")

            if "番地" in suffix:
                result["banchi"] = ban_val
                result["edaban"] = go_val
            else:
                result["ban"] = ban_val
                result["go"] = go_val
            tail = ban_match.group("tail").strip()
            return result, town, tail

        # =====================================================================
        # STATE 3: Hyphenated block notation (e.g. '6-10-1' or '10-1')
        # =====================================================================
        hyphen_match = re.search(
            r"^(?P<town>.*?)(?P<n1>\d+)-(?P<n2>\d+)(?:-(?P<n3>\d+))?(?P<tail>.*)$",
            text
        )
        if hyphen_match:
            town = hyphen_match.group("town").strip()
            n1 = int(hyphen_match.group("n1"))
            n2 = int(hyphen_match.group("n2"))
            n3 = int(hyphen_match.group("n3")) if hyphen_match.group("n3") else None

            if n3 is not None:
                # 3 numbers: Chome-Ban-Go
                result["chome"] = n1
                result["ban"] = n2
                result["go"] = n3
            else:
                # 2 numbers:
                if has_chome_already:
                    result["ban"] = n1
                    result["go"] = n2
                else:
                    # Conventional default: treat n1 as block (ban), n2 as house (go)
                    result["ban"] = n1
                    result["go"] = n2

            tail = hyphen_match.group("tail").strip()
            return result, town, tail

        # =====================================================================
        # STATE 4: Single number at tail of town (e.g. '488番地', '10番', or '1')
        # =====================================================================
        single_match = re.search(r"^(?P<town>.*?)(?P<num>\d+)(?:番地|番|号)?(?P<tail>.*)$", text)
        if single_match and single_match.group("num"):
            town = single_match.group("town").strip()
            num = int(single_match.group("num"))
            if "番地" in text:
                result["banchi"] = num
            else:
                result["ban"] = num
            tail = single_match.group("tail").strip()
            return result, town, tail

        # Default: Entire string is town name
        return result, text, ""
