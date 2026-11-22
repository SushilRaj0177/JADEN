"""JADEN: Finding addresses inside free text.

    extract_addresses('会場は東京都港区芝公園4-2-8の東京タワーです。TEL 03-3433-5111')
    -> one address, characters 3..17, '東京都港区芝公園4-2-8'

Emails, web pages, OCR output and CRM notes carry addresses in the middle of
other text. A span starts at a postal code, a prefecture name or a municipality
name, and ends where the address stops: at punctuation, a phone label, a
sentence particle after the house number, or the end of the line. Every span is
then resolved by the normal engine, and kept only if it really is an address:
a name that merely mentions a place ('東京タワー', '大阪城公園') is not.

Offsets refer to the text exactly as given, so spans can be highlighted or cut.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .models.address import NormalizedAddress

_MAX_SPAN = 90

_POSTAL = re.compile(r"(?:〒\s*)?[0-9０-９]{3}[-－‐ー−―][0-9０-９]{4}(?![0-9０-９-])|〒\s*[0-9０-９]{7}")
_PREFECTURE = re.compile(
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
    "新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|"
    "奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|"
    "熊本県|大分県|宮崎県|鹿児島県|沖縄県")

# Where an address certainly ends
_HARD_STOP = re.compile(
    r"[\n\r。！？!?、，,；;「」『』【】〔〕<>＜＞|｜/／\t]"
    r"|[（()）]"
    r"|\s{2,}|　{2,}"
    r"|\s*(?:TEL|Tel|tel|ＴＥＬ|電話|FAX|Fax|fax|ＦＡＸ|℡|☎|📞|E-?mail|Mail|メール|URL|https?:|www\.|営業時間|定休日|"
    r"アクセス|最寄り?駅|代表|担当|受付)")

# A sentence continuing right after the numbers: '…4-2-8の東京タワーです', '…4-2-8にあります'
_PARTICLE_AFTER_NUMBER = re.compile(
    r"(?<=[\d０-９号地番目階FfＦ室内外])"
    r"(?:の(?![\d０-９一二三四五六七八九十]|通|町|丁|割|坪|橋|宮|切|区|条|線)|に|で|へ|を|は|が|から|より|まで|です|にて|となり)")
# A number that counts something else ends the address before it: dates, times, prices, head counts
_NON_ADDRESS_NUMBER = re.compile(
    r"[\d０-９][\d０-９,，.．:：]*\s*(?:年|月|日|時|分|秒|円|名|人|歳|才|回|個|件|台|枚|点|％|%)")
_SENTENCE_TOKEN = re.compile(
    r"^(?:[にでへをはがのもと][ぁ-ん]|まで|より|から|にて|こちら|お越し|下さい|ください|です|ます|となり)"
    r"|(?:ください|下さい|します|しました|ました|でした|です|ます|ません|お越し|について|になります)")
_DIGIT = re.compile(r"[\d０-９一二三四五六七八九十]")


@dataclass(frozen=True, slots=True)
class ExtractedAddress:
    """One address found in a text."""
    start: int                    # offset of the first character in the original text
    end: int                      # offset just past the last character
    text: str                     # the span exactly as written
    canonical: str
    status: str                   # 'ACCEPTED' or 'AMBIGUOUS'
    lg_code: Optional[str]
    result: NormalizedAddress

    def to_dict(self) -> Dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text, "canonical": self.canonical,
                "status": self.status, "lg_code": self.lg_code, "postal_code": self.result.components.postal_code,
                "precision": self.result.precision, "latitude": self.result.latitude,
                "longitude": self.result.longitude}


def _span_end(text: str, start: int, body_start: int) -> int:
    """End offset of the address that starts at ``start`` (``body_start`` is past a leading postal code)."""
    limit = min(len(text), body_start + _MAX_SPAN)
    stop = _HARD_STOP.search(text, body_start, limit)
    end = stop.start() if stop else limit
    counted = _NON_ADDRESS_NUMBER.search(text, body_start, end)
    if counted:
        end = counted.start()
    # A sentence particle straight after the numbers ends the address
    first_digit = _DIGIT.search(text, body_start, end)
    if first_digit:
        particle = _PARTICLE_AFTER_NUMBER.search(text, first_digit.end(), end)
        if particle:
            end = particle.start()
    # Space-separated words after the address are kept while they look like a building, not a sentence
    segment = text[body_start:end]
    pieces = re.split(r"(\s+)", segment)
    kept = ""
    seen_number = False
    room_given = False
    for i in range(0, len(pieces), 2):
        word = pieces[i]
        if i > 0 and seen_number and (_SENTENCE_TOKEN.search(word) or room_given):
            break  # a sentence resumes, or the room number has already closed the address
        kept += (pieces[i - 1] if i > 0 else "") + word
        seen_number = seen_number or bool(_DIGIT.search(word))
        room_given = bool(re.search(r"[\d０-９]号室?$", word)) and i > 0
    return body_start + len(kept.rstrip())


def _anchors(text: str, engine: Any) -> List[Tuple[int, int, str]]:
    """(start, body start, kind) of every place an address may begin, in text order."""
    found: Dict[int, Tuple[int, int, str]] = {}
    for m in _POSTAL.finditer(text):
        body = m.end()
        gap = re.match(r"[ \t　]*(?:\r?\n)?[ \t　]*", text[body:])
        found[m.start()] = (m.start(), body + (gap.end() if gap else 0), "postal")
    for m in _PREFECTURE.finditer(text):
        found.setdefault(m.start(), (m.start(), m.start(), "prefecture"))
    trie = engine.admin_parser._muni_trie
    i = 0
    while i < len(text):
        ch = text[i]
        if "぀" <= ch <= "鿿" or ch in "ヶケ々":
            hit = trie.longest_prefix(text, i)
            if hit and len(hit[0]) >= 2:
                found.setdefault(i, (i, i, "municipality"))
                i += len(hit[0])
                continue
        i += 1
    return [found[k] for k in sorted(found)]


def extract_addresses(text: str, include_ambiguous: bool = True) -> List[ExtractedAddress]:
    """Finds the Japanese addresses in a text.

    Args:
        text: Any text: an email, a web page, OCR output, a CSV cell with notes.
        include_ambiguous: Also return addresses whose municipality is ambiguous (default True);
            their ``status`` is 'AMBIGUOUS' and ``lg_code`` is None.

    Returns:
        Addresses in text order, each with its exact span and its resolved result.
    """
    from .core.text import as_text
    from .engine import get_engine
    text = as_text(text)

    if not text:
        return []
    engine = get_engine()
    out: List[ExtractedAddress] = []
    cursor = 0
    for start, body_start, kind in _anchors(text, engine):
        if start < cursor:
            continue
        end = _span_end(text, start, body_start)
        if end <= body_start:
            continue
        span = text[start:end]
        res = engine.normalize(span)
        c = res.components
        if res.confidence_score <= 0:
            continue
        val = engine.validate(span)
        has_numbers = c.precision in ("block", "house", "unit")
        if val.status == "ACCEPTED":
            # A municipality name alone starts many ordinary words; it needs a block number after it.
            # After a prefecture or postal code, a registered town is enough.
            ok = has_numbers and (c.town_verified is not False or kind != "municipality") \
                or (kind != "municipality" and c.town_verified is True)
        elif val.status == "AMBIGUOUS":
            ok = include_ambiguous and has_numbers
        else:
            ok = False
        if not ok:
            continue
        out.append(ExtractedAddress(start, end, span, res.canonical, val.status, val.lg_code, res))
        cursor = end
    return out
