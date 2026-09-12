import { useMemo } from "react";
import { CATEGORIES, CATEGORY_LABELS, type RowInput } from "../types";
import { ERROR_MESSAGES, type RowError } from "../types";

interface RowFormProps {
  rows: RowInput[];
  errorsByRow: Map<number, RowError[]>;
  onChange: (index: number, next: RowInput) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onSubmit: () => void;
  onClear: () => void;
  submitting: boolean;
}

function fieldErrors(
  errorsByRow: Map<number, RowError[]>,
  index: number,
): { slot: RowError[]; containerId: RowError[]; category: RowError[] } {
  const all = errorsByRow.get(index) ?? [];
  return {
    slot: all.filter(
      (e) => e.field === "slot" || e.field === null || e.field === undefined,
    ),
    containerId: all.filter(
      (e) =>
        e.field === "container_id" ||
        e.field === null ||
        e.field === undefined,
    ),
    category: all.filter(
      (e) => e.field === "category" || e.field === null || e.field === undefined,
    ),
  };
}

export function RowForm({
  rows,
  errorsByRow,
  onChange,
  onAdd,
  onRemove,
  onSubmit,
  onClear,
  submitting,
}: RowFormProps) {
  const totalErrorRows = useMemo(
    () => errorsByRow.size,
    [errorsByRow],
  );

  return (
    <section aria-label="录入区">
      <div className="form-head">
        <h2>容器录入</h2>
        <div className="form-actions">
          <button type="button" onClick={onAdd} data-testid="add-row">
            ＋ 新增一行
          </button>
          <button type="button" onClick={onClear} data-testid="clear-rows">
            清空
          </button>
          <button
            type="button"
            className="primary"
            onClick={onSubmit}
            disabled={submitting}
            data-testid="submit"
          >
            {submitting ? "核验中…" : "提交核验"}
          </button>
        </div>
      </div>

      {totalErrorRows > 0 && (
        <p className="batch-banner" role="alert" data-testid="batch-banner">
          整批被拒绝(422):{totalErrorRows} 行存在问题,旧结论已清除,请修正标红行后重新提交。
        </p>
      )}

      <table className="row-table">
        <thead>
          <tr>
            <th className="col-idx">#</th>
            <th>库位号(1–99)</th>
            <th>容器编号(1–12 位大写字母/数字)</th>
            <th>类别</th>
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const f = fieldErrors(errorsByRow, index);
            return (
              <tr
                key={index}
                data-testid={`row-${index}`}
                className={errorsByRow.has(index) ? "row-error" : undefined}
              >
                <td className="col-idx">{index + 1}</td>
                <td>
                  <input
                    aria-label={`第 ${index + 1} 行库位号`}
                    data-testid={`slot-${index}`}
                    className={f.slot.length ? "invalid" : undefined}
                    value={row.slot}
                    inputMode="numeric"
                    onChange={(e) =>
                      onChange(index, { ...row, slot: e.target.value })
                    }
                  />
                  {f.slot.map((e, k) => (
                    <span className="field-error" key={k}>
                      {ERROR_MESSAGES[e.code] ?? e.code}
                      {e.code === "slot_over_capacity" && e.count != null
                        ? `(本批 ${e.count}/${e.limit ?? 4})`
                        : ""}
                    </span>
                  ))}
                </td>
                <td>
                  <input
                    aria-label={`第 ${index + 1} 行容器编号`}
                    data-testid={`container-${index}`}
                    className={f.containerId.length ? "invalid" : undefined}
                    value={row.containerId}
                    onChange={(e) =>
                      onChange(index, {
                        ...row,
                        containerId: e.target.value,
                      })
                    }
                  />
                  {f.containerId.map((e, k) => (
                    <span className="field-error" key={k}>
                      {ERROR_MESSAGES[e.code] ?? e.code}
                    </span>
                  ))}
                </td>
                <td>
                  <select
                    aria-label={`第 ${index + 1} 行类别`}
                    data-testid={`category-${index}`}
                    className={f.category.length ? "invalid" : undefined}
                    value={row.category}
                    onChange={(e) =>
                      onChange(index, {
                        ...row,
                        category: e.target.value as RowInput["category"],
                      })
                    }
                  >
                    <option value="">请选择</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {CATEGORY_LABELS[c]}
                      </option>
                    ))}
                  </select>
                  {f.category.map((e, k) => (
                    <span className="field-error" key={k}>
                      {ERROR_MESSAGES[e.code] ?? e.code}
                    </span>
                  ))}
                </td>
                <td>
                  <button
                    type="button"
                    aria-label={`删除第 ${index + 1} 行`}
                    data-testid={`remove-${index}`}
                    onClick={() => onRemove(index)}
                  >
                    删除
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
