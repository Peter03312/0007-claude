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
