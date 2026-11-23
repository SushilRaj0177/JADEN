"""Minimal Excel (.xlsx) reading and writing with the standard library only.

Reads the first worksheet as rows of text (shared strings, inline strings, numbers, booleans; never the
furigana Japanese Excel stores beside a string) and
writes one worksheet of text cells, so postal codes such as 0600063 keep their leading zero. Enough
for `jaden batch` and `jaden dedupe` to take a spreadsheet straight from Excel and give one back.
Hostile files are refused before they cost memory: parts too large or compressed too well, DTDs,
row and column numbers beyond Excel's limits, more than MAX_CELLS cells.
"""

import re
import zipfile
from pathlib import Path
from typing import IO, Dict, List, Optional, Sequence, Union
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CELL_REF = re.compile(r"([A-Z]+)(\d+)$")
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")
MAX_CELLS = 5_000_000
MAX_MATERIALIZED = 20_000_000                      # cells after padding each row to its last cell
MAX_ROWS, MAX_COLUMNS = 1_048_576, 16_384          # Excel's own limits
MAX_PART_BYTES = 512 * 1024 * 1024                  # one uncompressed part (a sheet, the shared strings)
# '<!DOCTYPE' and '<!ENTITY' in UTF-8 / ASCII and in UTF-16 (a part may declare either encoding)
_DTD_MARKS = tuple(word.encode(enc) for word in ("<!DOCTYPE", "<!ENTITY") for enc in ("ascii", "utf-16-le", "utf-16-be"))
MAX_RATIO = 200                                     # uncompressed / compressed: more is a zip bomb


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


def _local(tag: object) -> str:
    """A tag without its namespace: transitional and Strict OOXML name the same elements differently."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _kids(node: ET.Element, name: str) -> List[ET.Element]:
    return [child for child in node if _local(child.tag) == name]


def _kid(node: ET.Element, name: str) -> Optional[ET.Element]:
    return next((child for child in node if _local(child.tag) == name), None)


def _string_text(node: ET.Element) -> str:
    """The text of a shared or inline string: its own <t>, or the <t> of each rich-text run <r>. The
    phonetic runs (<rPh>: the furigana Japanese Excel stores) are not part of the text."""
    t = _kid(node, "t")
    if t is not None:
        return t.text or ""
    runs = (_kid(r, "t") for r in _kids(node, "r"))
    return "".join((t.text or "") for t in runs if t is not None)


def _number(value: str) -> str:
    """'105' stays '105'; '1.0' (how a whole number can be stored) becomes '1'."""
    try:
        f = float(value)
    except ValueError:
        return value
    return str(int(f)) if f.is_integer() and "e" not in value.lower() and abs(f) < 1e15 else value


def _open_part(book: zipfile.ZipFile, name: str, path: object) -> IO[bytes]:
    """A part of the package, refused when it is too large, compresses suspiciously well, or declares a DTD."""
    try:
        info = book.getinfo(name)
    except KeyError:
        raise ValueError(f"{path}: not a valid .xlsx file (missing {name})") from None
    if info.file_size > MAX_PART_BYTES or info.file_size > MAX_RATIO * max(info.compress_size, 1) + 1_000_000:
        raise ValueError(f"{path}: {name} is too large ({info.file_size:,} bytes uncompressed)")
    with book.open(info) as fh:                     # anywhere in the part, not only at its start
        previous = b""
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            window = previous + chunk
            if any(needle in window for needle in _DTD_MARKS):
                raise ValueError(f"{path}: {name} declares a DTD, which a spreadsheet never needs")
            previous = chunk[-40:]
    return book.open(info)


def _parse(book: zipfile.ZipFile, name: str, path: object) -> ET.Element:
    with _open_part(book, name, path) as fh:
        try:
            return ET.parse(fh).getroot()
        except ET.ParseError as exc:
            raise ValueError(f"{path}: {name} is not valid XML ({exc})") from None


def read_xlsx(path: Union[Path, IO[bytes]], sheet: int = 0) -> List[List[str]]:
    """The rows of one worksheet (the first by default) as lists of text. Rows with no cells are left out."""
    try:
        book = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise ValueError(f"{path} is not an .xlsx file") from None
    with book:
        names = set(book.namelist())
        shared: List[str] = []
        if "xl/sharedStrings.xml" in names:
            with _open_part(book, "xl/sharedStrings.xml", path) as fh:
                try:
                    for _event, node in ET.iterparse(fh):
                        if _local(node.tag) == "si":
                            shared.append(_string_text(node))
                            node.clear()
                            if len(shared) > MAX_CELLS:
                                raise ValueError(f"{path} has more than {MAX_CELLS:,} strings")
                except ET.ParseError as exc:
                    raise ValueError(f"{path}: the shared strings are not valid XML ({exc})") from None
        workbook = _parse(book, "xl/workbook.xml", path)
        sheets = [n for n in workbook.iter() if _local(n.tag) == "sheet"]
        if not sheets or sheet >= len(sheets):
            raise ValueError(f"{path} has no worksheet {sheet + 1}")
        rel_id = next((v for k, v in sheets[sheet].attrib.items() if _local(k) == "id"), None)
        rels = _parse(book, "xl/_rels/workbook.xml.rels", path)
        target = next((r.get("Target") for r in rels.iter() if _local(r.tag) == "Relationship"
                       and r.get("Id") == rel_id), None)
        if not target:
            raise ValueError(f"{path}: worksheet {sheet + 1} not found")
        target = target.lstrip("/")
        part = target if target.startswith("xl/") else f"xl/{target}"

        out: List[List[str]] = []
        cells = materialized = 0
        last_row = -1
        with _open_part(book, part, path) as fh:
            try:
                for _event, row in ET.iterparse(fh):
                    if _local(row.tag) != "row":
                        continue
                    r_attr = row.get("r")
                    number = int(r_attr) - 1 if r_attr and r_attr.isdigit() else last_row + 1
                    if not 0 <= number < MAX_ROWS or number <= last_row:
                        raise ValueError(f"{path}: row number {r_attr} is out of order or beyond Excel's limit")
                    last_row = number
                    values: Dict[int, str] = {}
                    for c_index, cell in enumerate(_kids(row, "c")):
                        cells += 1
                        if cells > MAX_CELLS:
                            raise ValueError(f"{path} has more than {MAX_CELLS:,} cells")
                        ref = _CELL_REF.match((cell.get("r") or "").upper())
                        if ref and len(ref.group(1)) > 3:
                            raise ValueError(f"{path}: cell {cell.get('r')} is beyond Excel's column limit")
                        col = _column_number(ref.group(1)) if ref else (max(values) + 1 if values else c_index)
                        if not 0 <= col < MAX_COLUMNS:
                            raise ValueError(f"{path}: cell {cell.get('r')} is beyond Excel's column limit")
                        kind = cell.get("t", "n")
                        v_node = _kid(cell, "v")
                        raw = (v_node.text if v_node is not None else "") or ""
                        if kind == "s":
                            value = shared[int(raw)] if raw.isdigit() and int(raw) < len(shared) else ""
                        elif kind == "inlineStr":
                            inline = _kid(cell, "is")
                            value = _string_text(inline) if inline is not None else ""
                        elif kind == "b":
                            value = "TRUE" if raw == "1" else "FALSE"
                        elif kind == "n":
                            value = _number(raw)
                        else:                       # 'str' (formula result), 'e' (error)
                            value = raw
                        values[col] = value
                    row.clear()
                    if values:
                        width = max(values) + 1
                        materialized += width
                        if materialized > MAX_MATERIALIZED:
                            # Sparse wide rows (one cell far to the right on every row) would be padded into
                            # millions of empty cells
                            raise ValueError(f"{path}: the rows are too wide to read ({materialized:,} cells "
                                             f"counting the empty ones)")
                        out.append([values.get(i, "") for i in range(width)])
            except ET.ParseError as exc:
                raise ValueError(f"{path}: the worksheet is not valid XML ({exc})") from None
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
