import type { SlotResult } from "../types";

interface ResultPanelProps {
  results: SlotResult[];
}

/**
 * 逐库位结论:通过 / 失败 + 规范化后的实际冲突对。
 * 结果已由后端按库位号数值升序、冲突对首项/次项 ASCII 字典序排好,
 * 前端只做原样呈现。
 */
export function ResultPanel({ results }: ResultPanelProps) {
  if (results.length === 0) {
    return (
      <section aria-label="核验结论" data-testid="results">
        <h2>逐库位结论</h2>
        <p className="muted" data-testid="results-empty">
          暂无结论:请录入容器后点击「提交核验」。
        </p>
      </section>
    );
  }

  const failed = results.filter((r) => !r.ok).length;

  return (
    <section aria-label="核验结论" data-testid="results">
      <h2>
        逐库位结论
        <span className="summary" data-testid="results-summary">
          共 {results.length} 个库位,{results.length - failed} 个通过,
          {failed} 个失败
        </span>
      </h2>
      <ul className="slot-list">
        {results.map((item) => (
          <li
            key={item.slot}
            className={`slot-card ${item.ok ? "ok" : "fail"}`}
            data-testid={`slot-result-${item.slot}`}
            data-slot={item.slot}
            data-ok={item.ok ? "true" : "false"}
          >
            <div className="slot-head">
              <span className="slot-no">库位 {item.slot}</span>
              <span
                className={`badge ${item.ok ? "badge-ok" : "badge-fail"}`}
                data-testid={`slot-status-${item.slot}`}
              >
                {item.ok ? "✓ 通过" : "✕ 失败"}
              </span>
              <span className="slot-containers">
                容器({item.container_ids.length}):
                {item.container_ids.join("、")}
              </span>
            </div>
            {!item.ok && (
              <div className="conflicts" data-testid={`conflicts-${item.slot}`}>
                <p>冲突容器对({item.conflicts.length}):</p>
                <ul>
                  {item.conflicts.map(([first, second], i) => (
                    <li
                      key={`${first}-${second}-${i}`}
                      data-testid={`conflict-${item.slot}-${i}`}
                    >
                      <code>{first}</code>
                      <span className="vs"> ⚠ </span>
                      <code>{second}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
