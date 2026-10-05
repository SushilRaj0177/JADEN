"""Unit tests for context-aware Japanese text sanitizer."""

from jaden.core.sanitizer import sanitize_address_text
from jaden.core.constants import DASH_VARIANTS


def test_nfkc_normalization():
    # Full-width numbers -> ASCII numbers
    assert sanitize_address_text("東京都千代田区１－２－３") == "東京都千代田区1-2-3"
    # Full-width alphabets -> ASCII
    assert sanitize_address_text("５０Ｆ") == "50F"


def test_unconditional_dash_variants():
    # Test each dash codepoint except contextual Choonpu
    for dash_char, (code, name, is_unconditional) in DASH_VARIANTS.items():
        if is_unconditional:
            inp = f"1{dash_char}2{dash_char}3"
            res = sanitize_address_text(inp)
            assert res == "1-2-3", f"Failed for {dash_char} ({code} {name})"


def test_contextual_choonpu_preservation():
    # Choonpu used between digits: must become hyphen
    assert sanitize_address_text("1ー2ー3") == "1-2-3"
    assert sanitize_address_text("六ー十ー一") == "六-十-一"

    # Choonpu inside Katakana proper loanwords: MUST be preserved
    assert sanitize_address_text("六本木ヒルズ森タワー") == "六本木ヒルズ森タワー"
    assert sanitize_address_text("東京ミッドタウンタワー") == "東京ミッドタウンタワー"
    assert sanitize_address_text("センタービル") == "センタービル"
    assert sanitize_address_text("ガーデンパレス") == "ガーデンパレス"


def test_whitespace_collapse():
    # Full-width Japanese space (U+3000), NBSP, tabs
    inp = "東京都　港区\u3000六本木\t6-10-1   森タワー"
    assert sanitize_address_text(inp) == "東京都 港区 六本木 6-10-1 森タワー"


def test_consecutive_hyphens():
    assert sanitize_address_text("1---2--3") == "1-2-3"


def test_box_drawing_dashes():
    assert sanitize_address_text("六本木1─2─3") == "六本木1-2-3"
    assert sanitize_address_text("六本木1━2━3") == "六本木1-2-3"
    assert sanitize_address_text("六本木1﹣2﹣3") == "六本木1-2-3"
    assert sanitize_address_text("六本木1﹘2﹘3") == "六本木1-2-3"


def test_newline_cr_collapse():
    assert sanitize_address_text("東京都港区六本木6-10-1\n改行") == "東京都港区六本木6-10-1 改行"
    assert sanitize_address_text("東京都\n港区\r\n六本木6-10-1") == "東京都 港区 六本木6-10-1"
    assert sanitize_address_text("東京都\r港区\r六本木") == "東京都 港区 六本木"


def test_postal_code_prefix_stripping():
    assert sanitize_address_text("〒106-0032 東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("106-0032 東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("〒106-0032東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("106-0032東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("〒1060032 東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("〒 東京都港区六本木6-10-1") == "東京都港区六本木6-10-1"
    assert sanitize_address_text("〒106-0032") == ""
    assert sanitize_address_text("106-0032") == ""
