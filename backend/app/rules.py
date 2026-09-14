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


@dataclass(frozen=True)
class _ParsedRow:
    """单行各字段独立解析结果。

    各字段独立合法、独立保留:某字段非法不会让该行其余合法字段
    从跨行检查中消失,保证一次提交就能同时暴露字段错误与
    重复编号/重复分配/超容量问题。
    """

    index: int
    slot: int | None
    container_id: str | None
    category: str | None


def _parse_row(index: int, raw: Any) -> tuple[_ParsedRow | None, list[dict[str, Any]]]:
    """逐字段校验单条录入;返回(各字段解析结果,行级错误列表)。

    行格式错误(非对象)时返回 None。字段级错误全部按原始行号上报,
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

    return (
        _ParsedRow(
            index=index,
            slot=slot if slot_ok else None,
            container_id=container_id if id_ok else None,
            category=category if category_ok else None,
        ),
        errors,
    )


def validate_batch(
    rows: list[dict[str, Any]],
) -> tuple[list[Assignment], list[dict[str, Any]]]:
    """整批校验。返回(合法录入列表,错误明细列表)。

    任一错误存在时,合法列表为空(整批拒绝,不产生任何结论)。
    所有 index 均为原始录入行号(从 0 开始),与字段非法行是否存在无关。
    一次提交即同时给出字段错误与全部跨行错误:
      - 重复编号:在所有"编号字段合法"的行之间检查,标出全部同号行;
      - 重复分配:在"编号、库位均合法"的行之间检查,标出全部同对行;
      - 超容量:该库位上所有"库位字段合法"的行都计入容量并全部标出。
    """

    parsed: list[_ParsedRow | None] = []
    errors: list[dict[str, Any]] = []

    for index, raw in enumerate(rows):
        row, row_errors = _parse_row(index, raw)
        parsed.append(row)
        errors.extend(row_errors)

    valid_rows = [row for row in parsed if row is not None]

    # 重复容器编号:全批唯一(即便去不同库位也不允许)。
    # 只比较编号字段合法的行,避免把非法编号误判成"重复"。
    id_rows: dict[str, list[int]] = defaultdict(list)
    for row in valid_rows:
        if row.container_id is not None:
            id_rows[row.container_id].append(row.index)
    for container_id, row_indices in id_rows.items():
        if len(row_indices) > 1:
            for i in row_indices:
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
    for row in valid_rows:
        if row.container_id is not None and row.slot is not None:
            pair_rows[(row.container_id, row.slot)].append(row.index)
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

    # 库位容量:每位最多 4 个容器。目标库位合法的行都计入容量,
    # 即使该行其他字段(编号/类别)非法,也不隐藏超容量问题。
    slot_rows: dict[int, list[int]] = defaultdict(list)
    for row in valid_rows:
        if row.slot is not None:
            slot_rows[row.slot].append(row.index)
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
        # 稳定排序:先按原始行号、再按错误码,前端标行与排查都有确定顺序
        errors.sort(key=lambda e: (e["index"], e["code"]))
        return [], errors

    assignments = [
        Assignment(slot=row.slot, container_id=row.container_id, category=row.category)  # type: ignore[arg-type]
        for row in valid_rows
    ]
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
