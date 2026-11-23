"""Minimal Excel (.xlsx) reading and writing with the standard library only.

Reads the first worksheet as rows of text (shared strings, inline strings, numbers, booleans) and
writes one worksheet of text cells, so postal codes such as 0600063 keep their leading zero. Enough
for `jaden batch` and `jaden dedupe` to take a spreadsheet straight from Excel and give one back.
"""

import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CELL_REF = re.compile(r"([A-Z]+)(\d+)")
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
MAX_CELLS = 20_000_000


def _column_number(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _column_letters(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _text(node: Optional[ET.Element]) -> str:
    """All <t> text inside a shared or inline string (rich text comes in runs)."""
    if node is None:
        return ""
    return "".join(t.text or "" for t in node.iter(f"{{{_NS['m']}}}t"))


def _number(value: str) -> str:
    """'105' stays '105'; '1.0' (how a whole number can be stored) becomes '1'."""
    try:
        f = float(value)
    except ValueError:
        return value
    return str(int(f)) if f.is_integer() and "e" not in value.lower() and abs(f) < 1e15 else value


def read_xlsx(path: Path, sheet: int = 0) -> List[List[str]]:
    """The rows of one worksheet (the first by default) as lists of text."""
    try:
        book = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise ValueError(f"{path} is not an .xlsx file") from None
    with book:
        names = set(book.namelist())
        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", _NS)]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        sheets = workbook.findall("m:sheets/m:sheet", _NS)
        if not sheets or sheet >= len(sheets):
            raise ValueError(f"{path} has no worksheet {sheet + 1}")
        rel_id = sheets[sheet].get(f"{{{_NS['r']}}}id")
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target = next((r.get("Target") for r in rels.findall("rel:Relationship", _NS) if r.get("Id") == rel_id), None)
        if target is None:
            raise ValueError(f"{path}: worksheet {sheet + 1} not found")
        target = target.lstrip("/")
        part = target if target.startswith("xl/") else f"xl/{target}"
        root = ET.fromstring(book.read(part))

    rows: Dict[int, Dict[int, str]] = {}
    cells = 0
    for r_index, row in enumerate(root.iter(f"{{{_NS['m']}}}row")):
        number = int(row.get("r") or r_index + 1) - 1
        values = rows.setdefault(number, {})
        for c_index, cell in enumerate(row.findall("m:c", _NS)):
            cells += 1
            if cells > MAX_CELLS:
                raise ValueError(f"{path} has more than {MAX_CELLS:,} cells")
            ref = _CELL_REF.match(cell.get("r") or "")
            col = _column_number(ref.group(1)) if ref else c_index
            kind = cell.get("t", "n")
            v = cell.find("m:v", _NS)
            raw = v.text if v is not None and v.text is not None else ""
            if kind == "s":
                value = shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
            elif kind == "inlineStr":
                value = _text(cell.find("m:is", _NS))
            elif kind == "b":
                value = "TRUE" if raw == "1" else "FALSE"
            elif kind == "n":
                value = _number(raw)
            else:                       # 'str' (formula result), 'e' (error)
                value = raw
            values[col] = value
    if not rows:
        return []
    out: List[List[str]] = []
    for number in range(max(rows) + 1):
        values = rows.get(number, {})
        out.append([values.get(i, "") for i in range(max(values) + 1)] if values else [])
    return out


def _cell(ref: str, value: object) -> str:
    text = _XML_ILLEGAL.sub("", "" if value is None else str(value))
    space = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{ref}" t="inlineStr"><is><t{space}>{escape(text)}</t></is></c>'


def write_xlsx(path: Path, rows: Sequence[Sequence[object]], sheet_name: str = "JADEN") -> None:
    """One worksheet of text cells; the first row is frozen as the header."""
    body = []
    for r, row in enumerate(rows, 1):
        cells = "".join(_cell(f"{_column_letters(c)}{r}", v) for c, v in enumerate(row) if v not in (None, ""))
        body.append(f'<row r="{r}">{cells}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet xmlns="{_NS["m"]}"><sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             f'<sheetData>{"".join(body)}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS["rel"]}"><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{_NS["m"]}" xmlns:r="{_NS["r"]}"><sheets>'
            f'<sheet name="{escape(sheet_name[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_NS["rel"]}"><Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        for name, content in files.items():
            book.writestr(name, content)
