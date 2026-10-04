"""Unit tests for BlockFSM (Chome-Ban-Go and Banchi-Edaban)."""

from jaden.parsers.fsm import BlockFSM


def test_fsm_named_gaiku():
    # '六本木6丁目10番1号'
    res, town, tail = BlockFSM.parse("六本木6丁目10番1号")
    assert town == "六本木"
    assert res["chome"] == 6
    assert res["ban"] == 10
    assert res["go"] == 1
    assert tail == ""


def test_fsm_named_chiban():
    # '上本能寺前町488番地1'
    res, town, tail = BlockFSM.parse("上本能寺前町488番地1")
    assert town == "上本能寺前町"
    assert res["banchi"] == 488
    assert res["edaban"] == 1
    assert tail == ""


def test_fsm_hyphenated_3_numbers():
    # '六本木6-10-1'
    res, town, tail = BlockFSM.parse("六本木6-10-1")
    assert town == "六本木"
    assert res["chome"] == 6
    assert res["ban"] == 10
    assert res["go"] == 1
    assert tail == ""


def test_fsm_hyphenated_2_numbers():
    # '明神町3-27'
    res, town, tail = BlockFSM.parse("明神町3-27")
    assert town == "明神町"
    assert res["ban"] == 3
    assert res["go"] == 27
    assert tail == ""


def test_fsm_with_tail_building():
    # '六本木6-10-1六本木ヒルズ森タワー50F'
    res, town, tail = BlockFSM.parse("六本木6-10-1六本木ヒルズ森タワー50F")
    assert town == "六本木"
    assert res["chome"] == 6
    assert res["ban"] == 10
    assert res["go"] == 1
    assert tail == "六本木ヒルズ森タワー50F"
