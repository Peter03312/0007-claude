"""危险品同位禁配核验规则引擎。

类别:
  A 酸类 / B 碱类 / O 氧化剂 / F 易燃品 / N 中性

无向禁配对: A-B、A-O、O-F,其余组合兼容。
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

CATEGORIES = frozenset({"A", "B", "O", "F", "N"})

# 无向禁配对(内部按 ASCII 排序存放,去重)
FORBIDDEN_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        tuple(sorted(p))  # type: ignore[misc]
        for p in (("A", "B"), ("A", "O"), ("O", "F"))
    }
)

MIN_SLOT = 1
MAX_SLOT = 99
MAX_CONTAINERS_PER_SLOT = 4
CONTAINER_RE = re.compile(r"^[A-Z0-9]{1,12}$")

# 整批 422 错误码
ERR_ROW_FORMAT = "row_format"
ERR_BAD_SLOT = "bad_slot"
ERR_BAD_CONTAINER_ID = "bad_container_id"
ERR_UNKNOWN_CATEGORY = "unknown_category"
ERR_DUPLICATE_ID = "duplicate_id"
ERR_DUPLICATE_ASSIGNMENT = "duplicate_assignment"
ERR_SLOT_OVER_CAPACITY = "slot_over_capacity"


@dataclass(frozen=True)
class Assignment:
    slot: int
    container_id: str
    category: str


def forbidden(a: str, b: str) -> bool:
    """两个类别是否构成无向禁配对。"""

    return tuple(sorted((a, b))) in FORBIDDEN_PAIRS


def _validate_row(
    index: int, raw: Any
) -> tuple[Assignment | None, list[dict[str, Any]]]:
    """校验单条录入;返回(合法时的 Assignment,行级错误列表)。

    行级错误只检查字段自身格式(库位号、容器编号、类别);
    跨行规则(重复编号、重复分配、超容量)在 validate_batch 中处理。
    """

    errors: list[dict[str, Any]] = []
    if not isinstance(raw, dict):
        errors.append(
            {"index": index, "code": ERR_ROW_FORMAT, "field": None}
        )
        return None, errors

    slot = raw.get("slot")
    container_id = raw.get("container_id")
    category = raw.get("category")

    slot_ok = (
        isinstance(slot, int)
        and not isinstance(slot, bool)
        and MIN_SLOT <= slot <= MAX_SLOT
    )
    if not slot_ok:
        errors.append({"index": index, "code": ERR_BAD_SLOT, "field": "slot"})

    id_ok = isinstance(container_id, str) and bool(
        CONTAINER_RE.fullmatch(container_id)
    )
    if not id_ok:
        errors.append(
            {
                "index": index,
                "code": ERR_BAD_CONTAINER_ID,
                "field": "container_id",
            }
        )

    category_ok = isinstance(category, str) and category in CATEGORIES
    if not category_ok:
        errors.append(
            {
                "index": index,
                "code": ERR_UNKNOWN_CATEGORY,
                "field": "category",
            }
        )

    if not (slot_ok and id_ok and category_ok):
        return None, errors
    return Assignment(slot=slot, container_id=container_id, category=category), []  # type: ignore[arg-type]


def validate_batch(
    rows: list[dict[str, Any]],
) -> tuple[list[Assignment], list[dict[str, Any]]]:
    """整批校验。返回(合法录入列表,错误明细列表)。

    任一错误存在时,合法列表为空(整批拒绝,不产生任何结论)。
    错误行标出方式:重复编号标所有同号行,重复分配标所有同对行,
    超容量标该库位上的所有行。
    """

    assignments: list[Assignment] = []
    errors: list[dict[str, Any]] = []

    for index, raw in enumerate(rows):
        assignment, row_errors = _validate_row(index, raw)
        errors.extend(row_errors)
        if assignment is not None:
            assignments.append(assignment)

    # 重复容器编号:全批唯一,一个编号只能出现一次(即便去不同库位也不允许)
    id_rows: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        id_rows[a.container_id].append(i)
    duplicate_id_rows: set[int] = set()
    for container_id, row_indices in id_rows.items():
        if len(row_indices) > 1:
            for i in row_indices:
                duplicate_id_rows.add(i)
                errors.append(
                    {
                        "index": i,
                        "code": ERR_DUPLICATE_ID,
                        "field": "container_id",
                        "container_id": container_id,
                    }
                )

    # 重复分配:同一(容器编号,目标库位)对出现两次以上
    pair_rows: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        pair_rows[(a.container_id, a.slot)].append(i)
    for (container_id, slot), row_indices in pair_rows.items():
        if len(row_indices) > 1:
            for i in row_indices:
                errors.append(
                    {
                        "index": i,
                        "code": ERR_DUPLICATE_ASSIGNMENT,
                        "field": None,
                        "container_id": container_id,
                        "slot": slot,
                    }
                )

    # 库位容量:每位最多 4 个容器
    slot_rows: dict[int, list[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        slot_rows[a.slot].append(i)
    for slot, row_indices in slot_rows.items():
        if len(row_indices) > MAX_CONTAINERS_PER_SLOT:
            for i in row_indices:
                errors.append(
                    {
                        "index": i,
                        "code": ERR_SLOT_OVER_CAPACITY,
                        "field": "slot",
                        "slot": slot,
                        "count": len(row_indices),
                        "limit": MAX_CONTAINERS_PER_SLOT,
                    }
                )

    if errors:
        return [], errors
    return assignments, []


def _pair_key(pair: tuple[str, str]) -> tuple[str, str]:
    """冲突对内部按容器编号 ASCII 字典序排列。"""

    return tuple(sorted(pair))  # type: ignore[return-value]


def verify(assignments: list[Assignment]) -> list[dict[str, Any]]:
    """对合法录入逐库位计算禁配结论。

    返回:
      [
        {
          "slot": 3,
          "ok": false,
          "container_ids": ["A1", "B2"],
          "conflicts": [["A1", "B2"]]
        },
        ...
      ]
    排序:库位号数值升序;冲突对先按首项、再按次项 ASCII 字典序。
    """

    by_slot: dict[int, list[Assignment]] = defaultdict(list)
    for a in assignments:
        by_slot[a.slot].append(a)

    results: list[dict[str, Any]] = []
    for slot in sorted(by_slot):
        items = by_slot[slot]
        conflicts: list[tuple[str, str]] = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                left, right = items[i], items[j]
                if forbidden(left.category, right.category):
                    conflicts.append(
                        _pair_key((left.container_id, right.container_id))
                    )
        conflicts = sorted(set(conflicts))
        results.append(
            {
                "slot": slot,
                "ok": not conflicts,
                "container_ids": sorted(
                    a.container_id for a in items
                ),
                "conflicts": [[first, second] for first, second in conflicts],
            }
        )
    return results
