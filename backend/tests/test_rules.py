"""规则引擎边界测试。"""

from __future__ import annotations

import pytest

from app.rules import (
    Assignment,
    MAX_CONTAINERS_PER_SLOT,
    forbidden,
    validate_batch,
    verify,
)


# ---------------------------------------------------------------- forbidden


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("A", "B", True),
        ("B", "A", True),  # 无向
        ("A", "O", True),
        ("O", "A", True),
        ("O", "F", True),
        ("F", "O", True),
        # 其余组合全部兼容
        ("A", "F", False),
        ("A", "N", False),
        ("B", "O", False),
        ("B", "F", False),
        ("B", "N", False),
        ("O", "N", False),
        ("F", "N", False),
        ("A", "A", False),
        ("N", "N", False),
    ],
)
def test_forbidden_matrix(a, b, expected):
    assert forbidden(a, b) is expected


# ---------------------------------------------------------------- verify


def r(slot, cid, cat) -> dict:
    return {"slot": slot, "container_id": cid, "category": cat}


def test_empty_batch_is_valid_and_empty():
    assignments, errors = validate_batch([])
    assert assignments == []
    assert errors == []
    assert verify(assignments) == []


def test_single_container_passes():
    assignments, errors = validate_batch([r(1, "A1", "A")])
    assert errors == []
    result = verify(assignments)
    assert result == [
        {"slot": 1, "ok": True, "container_ids": ["A1"], "conflicts": []}
    ]


def test_compatible_categories_pass():
    assignments, _ = validate_batch(
        [r(5, "A01", "A"), r(5, "F01", "F"), r(5, "N01", "N")]
    )
    (result,) = verify(assignments)
    assert result["ok"] is True
    assert result["conflicts"] == []


@pytest.mark.parametrize(
    "cats",
    [
        ["A", "B"],
        ["B", "A"],
        ["A", "O"],
        ["O", "A"],
        ["O", "F"],
        ["F", "O"],
    ],
)
def test_each_forbidden_pair_fails(cats):
    assignments, _ = validate_batch(
        [r(7, "CCC1", cats[0]), r(7, "CCC2", cats[1])]
    )
    (result,) = verify(assignments)
    assert result["ok"] is False
    assert result["conflicts"] == [["CCC1", "CCC2"]]


def test_conflict_pair_sorted_by_ascii_within_pair():
    # 录入顺序逆序时,冲突对内部仍按 ASCII 字典序
    assignments, _ = validate_batch(
        [r(2, "ZZZZ9", "B"), r(2, "AAAA1", "A")]
    )
    (result,) = verify(assignments)
    assert result["conflicts"] == [["AAAA1", "ZZZZ9"]]


def test_conflicts_sorted_by_first_then_second():
    assignments, _ = validate_batch(
        [
            r(3, "A3", "A"),
            r(3, "B1", "B"),
            r(3, "B2", "B"),
        ]
    )
    (result,) = verify(assignments)
    # A3 与两个 B 都冲突:先按首项 A3,再按次项 B1 < B2
    assert result["conflicts"] == [["A3", "B1"], ["A3", "B2"]]


def test_conflict_sorting_first_component_dominates():
    assignments, _ = validate_batch(
        [
            r(4, "B9", "B"),
            r(4, "A9", "A"),
            r(4, "A1", "A"),
        ]
    )
    (result,) = verify(assignments)
    # 规范化后: ["A1","B9"], ["A9","B9"],首项 A1 < A9
    assert result["conflicts"] == [["A1", "B9"], ["A9", "B9"]]


def test_results_sorted_by_slot_numeric():
    assignments, _ = validate_batch(
        [
            r(10, "X10", "A"),
            r(2, "X2", "B"),
            r(9, "X9", "O"),
        ]
    )
    slots = [item["slot"] for item in verify(assignments)]
    assert slots == [2, 9, 10]  # 数值序,不是 10,2,9 的字典序


def test_conflicts_never_cross_slots():
    assignments, _ = validate_batch(
        [r(1, "C1", "A"), r(2, "C2", "B")]  # 不同库位不比对
    )
    assert all(item["ok"] for item in verify(assignments))


def test_slot_capacity_boundary_four_ok_five_fails():
    rows = [r(8, f"C{i}", "N") for i in range(1, MAX_CONTAINERS_PER_SLOT + 2)]
    assignments, errors = validate_batch(rows)
    assert assignments == []
    codes = {e["code"] for e in errors}
    assert codes == {"slot_over_capacity"}
    # 超容量库位上的所有 5 行都被标出
    assert {e["index"] for e in errors} == {0, 1, 2, 3, 4}
    over = errors[0]
    assert over["slot"] == 8
    assert over["count"] == 5
    assert over["limit"] == 4


def test_exactly_four_containers_per_slot_passes():
    rows = [r(8, f"C{i}", "N") for i in range(1, MAX_CONTAINERS_PER_SLOT + 1)]
    assignments, errors = validate_batch(rows)
    assert errors == []
    (result,) = verify(assignments)
    assert result["ok"] is True


def test_capacity_counts_per_slot_independently():
    rows = [r(1, f"A{i}", "N") for i in range(5)]
    rows += [r(2, f"B{i}", "N") for i in range(4)]
    _, errors = validate_batch(rows)
    assert {e["index"] for e in errors} == {0, 1, 2, 3, 4}


# ------------------------------------------------------------ row 422 rules


def test_slot_bounds_one_and_ninety_nine_ok():
    for slot in (1, 99):
        _, errors = validate_batch([r(slot, "C1", "N")])
        assert errors == []


@pytest.mark.parametrize("slot", [0, -1, 100, 999])
def test_slot_out_of_range(slot):
    _, errors = validate_batch([r(slot, "C1", "N")])
    assert [e["code"] for e in errors] == ["bad_slot"]
    assert errors[0]["index"] == 0
    assert errors[0]["field"] == "slot"


def test_slot_must_be_integer():
    _, errors = validate_batch([{"slot": "3", "container_id": "C1", "category": "N"}])
    assert [e["code"] for e in errors] == ["bad_slot"]


def test_slot_boolean_rejected():
    _, errors = validate_batch([r(True, "C1", "N")])
    assert [e["code"] for e in errors] == ["bad_slot"]


def test_container_id_length_boundaries():
    assert validate_batch([r(1, "A", "N")])[1] == []
    assert validate_batch([r(1, "A" * 12, "N")])[1] == []
    codes = [e["code"] for e in validate_batch([r(1, "", "N")])[1]]
    assert codes == ["bad_container_id"]
    codes = [e["code"] for e in validate_batch([r(1, "A" * 13, "N")])[1]]
    assert codes == ["bad_container_id"]


def test_container_id_charset():
    assert validate_batch([r(1, "AB12ZZ", "N")])[1] == []
    for bad in ["abc1", "A-1", "A 1", "A_1", "容器", "1.5"]:
        errors = validate_batch([r(1, bad, "N")])[1]
        assert [e["code"] for e in errors] == ["bad_container_id"], bad


def test_unknown_category_rejected():
    _, errors = validate_batch([r(1, "C1", "X")])
    assert [e["code"] for e in errors] == ["unknown_category"]
    assert errors[0]["field"] == "category"


def test_lowercase_category_rejected():
    _, errors = validate_batch([r(1, "C1", "a")])
    assert [e["code"] for e in errors] == ["unknown_category"]


def test_duplicate_id_marks_all_rows_even_across_slots():
    _, errors = validate_batch(
        [r(1, "DUP1", "A"), r(2, "DUP1", "B"), r(3, "OK1", "N")]
    )
    dup = [e for e in errors if e["code"] == "duplicate_id"]
    assert {e["index"] for e in dup} == {0, 1}
    assert all(e["container_id"] == "DUP1" for e in dup)


def test_duplicate_assignment_same_slot_same_id():
    _, errors = validate_batch(
        [r(5, "DUP1", "A"), r(5, "DUP1", "B")]
    )
    codes = {e["code"] for e in errors}
    # 既是重复编号,也是重复分配
    assert codes == {"duplicate_id", "duplicate_assignment"}
    dup_assign = [e for e in errors if e["code"] == "duplicate_assignment"]
    assert {e["index"] for e in dup_assign} == {0, 1}
    assert dup_assign[0]["slot"] == 5


def test_same_id_different_slot_is_duplicate_id_but_not_assignment():
    _, errors = validate_batch([r(1, "DUP1", "N"), r(2, "DUP1", "N")])
    codes = {e["code"] for e in errors}
    assert "duplicate_id" in codes
    assert "duplicate_assignment" not in codes


def test_non_object_row_marked():
    assignments, errors = validate_batch(["nonsense"])
    assert assignments == []
    assert errors[0] == {"index": 0, "code": "row_format", "field": None}


def test_multiple_field_errors_same_row():
    _, errors = validate_batch(
        [{"slot": 0, "container_id": "小写bad", "category": "X"}]
    )
    assert {e["code"] for e in errors} == {
        "bad_slot",
        "bad_container_id",
        "unknown_category",
    }


def test_errors_from_later_rows_do_not_drown_earlier_ones():
    _, errors = validate_batch(
        [
            r(1, "OK1", "N"),
            {"slot": 200, "container_id": "OK2", "category": "A"},
            r(3, "OK3", "Z"),
        ]
    )
    by_index: dict[int, set[str]] = {}
    for e in errors:
        by_index.setdefault(e["index"], set()).add(e["code"])
    assert by_index == {1: {"bad_slot"}, 2: {"unknown_category"}}


def test_batch_rejected_when_any_error_returns_no_assignments():
    assignments, errors = validate_batch(
        [r(1, "OK1", "A"), r(1, "OK2", "B"), r(1, "BAD!", "N")]
    )
    assert assignments == []
    assert any(e["code"] == "bad_container_id" for e in errors)


def test_three_way_forbidden_mixture_lists_all_pairs():
    # A-B 冲突;A-O 冲突;B-O 兼容 => 两对
    assignments, _ = validate_batch(
        [r(6, "AA", "A"), r(6, "BB", "B"), r(6, "OO", "O")]
    )
    (result,) = verify(assignments)
    assert result["ok"] is False
    assert result["conflicts"] == [["AA", "BB"], ["AA", "OO"]]


# -------------------------------------------- 缺陷回归:行号错位/问题隐藏


def test_field_error_in_first_row_does_not_shift_later_row_indices():
    # 第 0 行库位越界;第 1、2 行编号重复。旧实现会把重复标到 0、1 行。
    _, errors = validate_batch(
        [
            {"slot": 0, "container_id": "GOODID", "category": "N"},
            r(2, "DUP1", "A"),
            r(3, "DUP1", "B"),
        ]
    )
    dup = [e for e in errors if e["code"] == "duplicate_id"]
    assert {e["index"] for e in dup} == {1, 2}
    bad_slot = [e for e in errors if e["code"] == "bad_slot"]
    assert {e["index"] for e in bad_slot} == {0}


def test_multiple_field_errors_before_duplicate_keep_original_indices():
    # 前两行各有字段错误(过滤后列表只剩第三行起),后续重复仍须标真实行号
    _, errors = validate_batch(
        [
            {"slot": 5, "container_id": "bad-id", "category": "N"},
            {"slot": 7, "container_id": "GOOD1", "category": "X"},
            r(1, "SAME", "N"),
            r(2, "SAME", "N"),
        ]
    )
    dup = [e for e in errors if e["code"] == "duplicate_id"]
    assert {e["index"] for e in dup} == {2, 3}
    # 无关的第 2、3 行本身字段合法,不被任何字段错误牵连
    assert all(
        e["index"] not in (2, 3)
        for e in errors
        if e["code"].startswith("bad_") or e["code"] == "unknown_category"
    )


def test_field_error_before_over_capacity_marks_correct_rows():
    # 第 0 行库位非法(不参与容量);第 1..5 行库位 8 共 5 个 => 超容量
    rows = [
        {"slot": 100, "container_id": "C0", "category": "N"},
        *[r(8, f"C{i}", "N") for i in range(1, 6)],
    ]
    _, errors = validate_batch(rows)
    over = [e for e in errors if e["code"] == "slot_over_capacity"]
    assert {e["index"] for e in over} == {1, 2, 3, 4, 5}
    assert all(e["count"] == 5 for e in over)
    # 第 0 行只报自己的库位错误,不被错标成超容量
    row0 = [e for e in errors if e["index"] == 0]
    assert [e["code"] for e in row0] == ["bad_slot"]


def test_row_with_bad_category_still_participates_in_duplicate_id():
    # 编号合法但类别非法的行,其编号重复问题必须同批暴露
    _, errors = validate_batch(
        [
            r(1, "DUPX", "N"),
            {"slot": 2, "container_id": "DUPX", "category": "Z"},
        ]
    )
    codes_by_index: dict[int, set[str]] = {}
    for e in errors:
        codes_by_index.setdefault(e["index"], set()).add(e["code"])
    assert codes_by_index == {
        0: {"duplicate_id"},
        1: {"unknown_category", "duplicate_id"},
    }


def test_row_with_bad_id_still_counts_toward_slot_capacity():
    # 库位合法、编号非法的行也计入容量:5 行同库位须同批报超容量
    rows = [
        {"slot": 4, "container_id": "lower", "category": "N"},
        *[r(4, f"C{i}", "N") for i in range(1, 5)],
    ]
    _, errors = validate_batch(rows)
    over = [e for e in errors if e["code"] == "slot_over_capacity"]
    assert {e["index"] for e in over} == {0, 1, 2, 3, 4}
    # 第 0 行同时有编号错误与超容量,一次性都给出
    row0 = {e["code"] for e in errors if e["index"] == 0}
    assert row0 == {"bad_container_id", "slot_over_capacity"}


def test_all_problems_on_one_row_reported_together():
    # 单行:库位越界 + 编号非法 + 类别非法,三个错误一次给全
    _, errors = validate_batch(
        [{"slot": 0, "container_id": "小写bad", "category": "?"}]
    )
    assert {e["code"] for e in errors} == {
        "bad_slot",
        "bad_container_id",
        "unknown_category",
    }


def test_field_errors_and_over_capacity_and_duplicate_all_in_one_batch():
    # 综合场景:
    #   行 0:库位 9 编号非法(仍计入库位 9 容量)
    #   行 1..3:库位 9 合法行(库位 9 共 4 行,未超)
    #   行 4:库位 9 合法行(库位 9 变 5 行 => 全部标超容量)
    #   行 5、6:库位 1、2 同号 DUP => 重复编号
    rows = [
        {"slot": 9, "container_id": "bad", "category": "N"},
        *[r(9, f"OK{i}", "N") for i in range(1, 5)],
        r(1, "DUP", "N"),
        r(2, "DUP", "N"),
    ]
    _, errors = validate_batch(rows)
    codes_by_index: dict[int, set[str]] = {}
    for e in errors:
        codes_by_index.setdefault(e["index"], set()).add(e["code"])

    assert codes_by_index[0] == {"bad_container_id", "slot_over_capacity"}
    for i in (1, 2, 3, 4):
        assert codes_by_index[i] == {"slot_over_capacity"}
    assert codes_by_index[5] == {"duplicate_id"}
    assert codes_by_index[6] == {"duplicate_id"}


def test_bad_slot_row_excluded_from_capacity_but_own_error_shown():
    # 库位字段非法的行无法计入任何库位容量,只报自身字段错误
    rows = [
        {"slot": 500, "container_id": "C0", "category": "N"},
        *[r(3, f"C{i}", "N") for i in range(1, 5)],
    ]
    _, errors = validate_batch(rows)
    assert [e["code"] for e in errors if e["index"] == 0] == ["bad_slot"]
    assert not [e for e in errors if e["code"] == "slot_over_capacity"]


def test_error_detail_sorted_by_index_then_code():
    _, errors = validate_batch(
        [
            r(1, "DUP", "N"),
            {"slot": 0, "container_id": "bad!", "category": "X"},
            r(2, "DUP", "N"),
        ]
    )
    keys = [(e["index"], e["code"]) for e in errors]
    assert keys == sorted(keys)

